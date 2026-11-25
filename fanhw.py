"""Hardware access for HP OMEN fans via the kernel hp-wmi hwmon interface.

The hp-wmi driver exposes `pwm1_enable` with two accepted values:
  0 = fans at maximum speed
  2 = automatic (firmware fan curve)
There is no per-percentage control on this platform.
"""

from dataclasses import dataclass
from pathlib import Path

HWMON_ROOT = Path("/sys/class/hwmon")
MODE_MAX = "max"
MODE_AUTO = "auto"
_PWM_VALUE = {MODE_MAX: "0", MODE_AUTO: "2"}
_PWM_MODE = {v: k for k, v in _PWM_VALUE.items()}


class FanError(Exception):
    """Raised when the fan interface is missing or not writable."""


@dataclass(frozen=True)
class Reading:
    fan1_rpm: int
    fan2_rpm: int
    cpu_temp_c: float
    hw_mode: str  # "auto", "max" or "unknown"


def _find_hwmon(name: str) -> Path | None:
    for hw in sorted(HWMON_ROOT.glob("hwmon*")):
        try:
            if (hw / "name").read_text().strip() == name:
                return hw
        except OSError:
            continue
    return None


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return default


class OmenFans:
    def __init__(self) -> None:
        self.fan_dir = _find_hwmon("hp")
        self.temp_dir = _find_hwmon("coretemp")
        if self.fan_dir is None or not (self.fan_dir / "pwm1_enable").exists():
            raise FanError("hp-wmi fan interface not found (is the hp_wmi module loaded?)")

    @property
    def pwm_path(self) -> Path:
        return self.fan_dir / "pwm1_enable"

    def writable(self) -> bool:
        import os
        return os.access(self.pwm_path, os.W_OK)

    def read(self) -> Reading:
        raw_mode = ""
        try:
            raw_mode = self.pwm_path.read_text().strip()
        except OSError:
            pass
        temp = 0.0
        if self.temp_dir is not None:
            # temp1 is the CPU package sensor on coretemp
            temp = _read_int(self.temp_dir / "temp1_input") / 1000.0
        return Reading(
            fan1_rpm=_read_int(self.fan_dir / "fan1_input"),
            fan2_rpm=_read_int(self.fan_dir / "fan2_input"),
            cpu_temp_c=temp,
            hw_mode=_PWM_MODE.get(raw_mode, "unknown"),
        )

    def set_mode(self, mode: str) -> None:
        if mode not in _PWM_VALUE:
            raise ValueError(f"invalid fan mode: {mode!r}")
        try:
            self.pwm_path.write_text(_PWM_VALUE[mode])
        except PermissionError as exc:
            raise FanError("No permission to change fan mode. Run install.sh once.") from exc
        except OSError as exc:
            raise FanError(f"Firmware rejected fan mode {mode}: {exc.strerror}") from exc


def smart_target(temp_c: float, threshold_c: float, hysteresis_c: float, current: str) -> str:
    """Pick the hardware mode for Smart mode.

    Boost to max at or above the threshold; drop back to auto only once the
    temperature falls below threshold - hysteresis, so the fans don't flap.
    """
    if temp_c >= threshold_c:
        return MODE_MAX
    if current == MODE_MAX and temp_c > threshold_c - hysteresis_c:
        return MODE_MAX
    return MODE_AUTO
