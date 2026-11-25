#!/usr/bin/env python3
"""OMEN Fan Control: a small GTK3 app for HP OMEN fan modes."""

import json
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fanhw import MODE_AUTO, MODE_MAX, FanError, OmenFans, smart_target  # noqa: E402

POLL_MS = 1500
HYSTERESIS_C = 8.0
RPM_SCALE_MIN = 5800  # grows if the fans report higher
CONFIG_PATH = Path.home() / ".config" / "omen-fan" / "config.json"
DEFAULT_CONFIG = {"mode": "auto", "threshold": 80}
MODES = [("auto", "Auto"), ("smart", "Smart"), ("max", "Max")]
MODE_HINTS = {
    "auto": "Firmware controls the fans.",
    "smart": "Fans go to max above the temperature below, back to auto when it cools.",
    "max": "Fans run at full speed.",
}

CSS = b"""
.title { font-size: 18px; font-weight: 700; }
.rpm { font-size: 26px; font-weight: 700; font-feature-settings: "tnum"; }
.temp { font-size: 34px; font-weight: 700; font-feature-settings: "tnum"; }
.dim { opacity: 0.65; }
.card { border-radius: 12px; padding: 12px; background-color: alpha(@theme_fg_color, 0.06); }
.hot { color: #e5534b; }
.warm { color: #d29922; }
.status-err { color: #e5534b; }
levelbar block.filled { background-color: #3d8bfd; border-radius: 4px; }
levelbar block.empty { border-radius: 4px; }
"""


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)
    mode = data.get("mode") if data.get("mode") in dict(MODES) else DEFAULT_CONFIG["mode"]
    try:
        threshold = min(95, max(55, int(data.get("threshold", 80))))
    except (TypeError, ValueError):
        threshold = DEFAULT_CONFIG["threshold"]
    return {"mode": mode, "threshold": threshold}


def save_config(config: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config))
    except OSError as exc:
        print(f"could not save config: {exc}", file=sys.stderr)


def label(text: str = "", css: tuple = (), xalign: float = 0.0) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=xalign)
    for cls in css:
        lbl.get_style_context().add_class(cls)
    return lbl


class FanWindow(Gtk.Window):
    def __init__(self, fans: OmenFans) -> None:
        super().__init__(title="OMEN Fan Control")
        self.fans = fans
        self.config = load_config()
        self.rpm_scale = RPM_SCALE_MIN
        self.applied_hw_mode = None
        self.set_default_size(380, -1)
        self.set_resizable(False)
        self.set_border_width(16)
        self.connect("delete-event", self.on_close)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add(root)
        root.pack_start(label("OMEN Fan Control", ("title",)), False, False, 0)
        root.pack_start(self._build_temp_card(), False, False, 0)
        root.pack_start(self._build_fans_card(), False, False, 0)
        root.pack_start(self._build_mode_box(), False, False, 0)
        self.status = label("", ("dim",))
        self.status.set_line_wrap(True)
        root.pack_start(self.status, False, False, 0)

        self._select_mode(self.config["mode"])
        self.tick()
        GLib.timeout_add(POLL_MS, self.tick)

    # ---- layout ---------------------------------------------------------
    def _build_temp_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        card.get_style_context().add_class("card")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left.pack_start(label("CPU temperature", ("dim",)), False, False, 0)
        self.temp_label = label("--", ("temp",))
        left.pack_start(self.temp_label, False, False, 0)
        card.pack_start(left, True, True, 0)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.set_valign(Gtk.Align.CENTER)
        right.pack_start(label("Fan state", ("dim",), 1.0), False, False, 0)
        self.hw_label = label("--", (), 1.0)
        right.pack_start(self.hw_label, False, False, 0)
        card.pack_end(right, False, False, 0)
        return card

    def _build_fans_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("card")
        self.fan_widgets = []
        for name in ("CPU fan", "GPU fan"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.pack_start(label(name, ("dim",)), True, True, 0)
            rpm = label("--", ("rpm",), 1.0)
            row.pack_end(rpm, False, False, 0)
            bar = Gtk.LevelBar(min_value=0, max_value=1)
            bar.set_size_request(-1, 8)
            for offset in ("low", "high", "full"):
                bar.remove_offset_value(offset)
            card.pack_start(row, False, False, 0)
            card.pack_start(bar, False, False, 0)
            self.fan_widgets.append((rpm, bar))
        return card

    def _build_mode_box(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        switcher = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True)
        switcher.get_style_context().add_class("linked")
        self.mode_buttons = {}
        group = None
        for key, text in MODES:
            btn = Gtk.RadioButton.new_with_label_from_widget(group, text)
            btn.set_mode(False)  # draw as a toggle button, not a radio dot
            btn.connect("toggled", self.on_mode_toggled, key)
            group = group or btn
            switcher.pack_start(btn, True, True, 0)
            self.mode_buttons[key] = btn
        box.pack_start(switcher, False, False, 0)
        self.mode_hint = label("", ("dim",))
        self.mode_hint.set_line_wrap(True)
        box.pack_start(self.mode_hint, False, False, 0)

        self.smart_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.smart_box.pack_start(label("Boost at"), False, False, 0)
        self.threshold = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 55, 95, 1)
        self.threshold.set_value(self.config["threshold"])
        self.threshold.set_value_pos(Gtk.PositionType.RIGHT)
        self.threshold.connect("format-value", lambda _s, v: f"{v:.0f} °C")
        self.threshold.connect("value-changed", self.on_threshold_changed)
        self.smart_box.pack_start(self.threshold, True, True, 0)
        box.pack_start(self.smart_box, False, False, 0)
        return box

    # ---- behaviour ------------------------------------------------------
    def _select_mode(self, mode: str) -> None:
        self.mode_buttons[mode].set_active(True)
        self._mode_changed(mode)

    def _mode_changed(self, mode: str) -> None:
        self.config = {**self.config, "mode": mode}
        save_config(self.config)
        self.mode_hint.set_text(MODE_HINTS[mode])
        self.smart_box.set_sensitive(mode == "smart")
        self.applied_hw_mode = None  # force re-apply on next tick
        self.tick()

    def on_mode_toggled(self, button: Gtk.RadioButton, mode: str) -> None:
        if button.get_active() and mode != self.config["mode"]:
            self._mode_changed(mode)

    def on_threshold_changed(self, scale: Gtk.Scale) -> None:
        self.config = {**self.config, "threshold": int(scale.get_value())}
        save_config(self.config)

    def desired_hw_mode(self, temp: float, current: str) -> str:
        mode = self.config["mode"]
        if mode == "smart":
            return smart_target(temp, self.config["threshold"], HYSTERESIS_C, current)
        return MODE_MAX if mode == "max" else MODE_AUTO

    def tick(self) -> bool:
        reading = self.fans.read()
        target = self.desired_hw_mode(reading.cpu_temp_c, reading.hw_mode)
        # Re-apply whenever the firmware state drifts from what we want.
        if target != reading.hw_mode or target != self.applied_hw_mode:
            try:
                if target != reading.hw_mode:
                    self.fans.set_mode(target)
                self.applied_hw_mode = target
                self._set_status("")
            except FanError as exc:
                self._set_status(str(exc), error=True)
        self._render(reading, target)
        return True

    def _render(self, reading, target: str) -> None:
        temp = reading.cpu_temp_c
        self.temp_label.set_text(f"{temp:.0f} °C")
        ctx = self.temp_label.get_style_context()
        for cls in ("hot", "warm"):
            ctx.remove_class(cls)
        if temp >= 90:
            ctx.add_class("hot")
        elif temp >= 75:
            ctx.add_class("warm")
        self.hw_label.set_markup(f"<b>{'Max' if target == MODE_MAX else 'Auto'}</b>")
        rpms = (reading.fan1_rpm, reading.fan2_rpm)
        self.rpm_scale = max(self.rpm_scale, *rpms)
        for (rpm_label, bar), rpm in zip(self.fan_widgets, rpms):
            rpm_label.set_text(f"{rpm:,} RPM")
            bar.set_value(min(1.0, rpm / self.rpm_scale))

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.set_text(text)
        ctx = self.status.get_style_context()
        (ctx.add_class if error else ctx.remove_class)("status-err")

    def on_close(self, *_args) -> bool:
        # Hand control back to the firmware so fans never stay pinned at max.
        try:
            self.fans.set_mode(MODE_AUTO)
        except FanError as exc:
            print(f"could not restore auto mode: {exc}", file=sys.stderr)
        Gtk.main_quit()
        return False


def main() -> int:
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    from gi.repository import Gdk
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    try:
        fans = OmenFans()
    except FanError as exc:
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE, text=str(exc))
        dialog.run()
        return 1
    win = FanWindow(fans)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, win.on_close)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, win.on_close)
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
