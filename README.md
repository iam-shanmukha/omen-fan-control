# OMEN Fan Control: HP OMEN fan control for Ubuntu and Linux

A simple GUI to control the fans on **HP OMEN** (and possibly **HP Victus**) gaming laptops running **Ubuntu** or other Linux distros. Switch between **Auto**, **Smart** and **Max** fan modes, and watch CPU temperature and fan RPM live.

It's a lightweight Linux alternative to the fan control in Windows' **OMEN Gaming Hub**. It needs **no kernel patch**: it works on the stock Ubuntu kernel, so there's nothing to compile, nothing to rebuild after kernel updates, and nothing to sign for Secure Boot. If you need exact fan speeds or custom curves, see [Similar projects](#similar-projects).

![OMEN Fan Control on Ubuntu: CPU temperature, CPU and GPU fan RPM, Auto / Smart / Max buttons](docs/screenshot.png)

| Mode | What it does |
|---|---|
| **Auto** | The firmware controls the fans. |
| **Smart** | Switches to Max once the CPU reaches the temperature you pick (55–95 °C), and back to Auto when it cools 8 °C below that. |
| **Max** | Both fans at full speed. |

Closing the window puts the fans back to Auto, so they never stay stuck at full speed.

## Supported laptops

| Laptop | Board ID | Distro | Kernel | Status |
|---|---|---|---|---|
| HP OMEN Slim Gaming Laptop 16t-an000 | 8D40 | Ubuntu 24.04 | 6.14 | ✅ Works |

**Have a different HP OMEN or Victus?** Run `./check-compat.sh` and [open a compatibility report](https://github.com/iam-shanmukha/omen-fan-control/issues/new?template=compatibility.yml), even if it doesn't work. Each report adds a row here, which helps the next person with the same laptop.

Your laptop probably works if `./check-compat.sh` prints `Result: SUPPORTED`.

## Install on Ubuntu

```sh
git clone https://github.com/iam-shanmukha/omen-fan-control.git
cd omen-fan-control
./check-compat.sh   # confirm your laptop is supported
./install.sh
```

Then open **OMEN Fan Control** from the app menu, or run `python3 omen_fan_gui.py`.

`install.sh` adds the udev rule `/etc/udev/rules.d/99-omen-fan.rules`, which lets members of the `sudo` group change the fan mode without a password prompt, plus an app-menu entry.

Requirements: Python 3.10+ with GTK 3 bindings (`python3-gi`, preinstalled on Ubuntu with GNOME) and the `hp_wmi` kernel module (loaded automatically on HP laptops).

## FAQ

### How do I set HP OMEN fans to max speed on Linux?

Pick **Max** in the app. Under the hood this writes `0` to `pwm1_enable` on the `hp` hwmon device, which is the same thing as:

```sh
HP=$(dirname "$(grep -lx hp /sys/class/hwmon/hwmon*/name)")
echo 0 | sudo tee "$HP/pwm1_enable"   # max
echo 2 | sudo tee "$HP/pwm1_enable"   # auto
```

### Why can't I set the fan speed to a percentage?

The Linux `hp-wmi` driver only accepts two values for these laptops: `0` (max) and `2` (auto). Anything else returns `Invalid argument`. Smart mode is a temperature-triggered boost built on top of those two states.

Newer kernels add manual fan control for some boards, and the patched-driver projects under [Similar projects](#similar-projects) backport it, if you're comfortable installing a kernel module.

### My HP OMEN laptop overheats on Ubuntu. Will this help?

Smart mode boosts the fans before the CPU gets too hot, without running them at full noise all the time. Set the threshold around 75–80 °C.

### Does it work with NBFC?

This app doesn't need NBFC or `fancontrol`. It uses the kernel's own `hp-wmi` driver.

## Similar projects

Pick OMEN Fan Control if you want something simple that runs on the stock kernel. Pick one of these if you want exact fan speeds, custom curves or keyboard RGB, and you're fine installing a patched kernel driver.

| Project | Approach | Highlights |
|---|---|---|
| [arfelious/omen-fan-control](https://github.com/arfelious/omen-fan-control) | Patched `hp-wmi` driver | CLI + GUI, RPM control and curves, tested on many OMEN / Victus boards and Ubuntu 24.04 |
| [Batuhan4/victus-control](https://github.com/Batuhan4/victus-control) | Patched `hp-wmi` driver | GTK4 app + GNOME Shell extension, fan curve, manual RPM steps, keyboard RGB |
| [emomaxd/hpfand](https://github.com/emomaxd/hpfand) | Kernel `hp_wmi` PWM | Background daemon with silent / balanced / performance curves, CLI |
| [noahpro99/omenix](https://github.com/noahpro99/omenix) | Kernel `hp-wmi` | System tray app; needs your board in the driver's list |
| [TUXOV/hp-wmi-fan-and-backlight-control](https://github.com/TUXOV/hp-wmi-fan-and-backlight-control) | Out-of-tree kernel module | The patched driver several of these tools build on |
| [alou-S/omen-fan](https://github.com/alou-S/omen-fan) | Direct EC writes | For specific older Omen 16 models |

Windows users: [OmenSuperHub](https://github.com/breadeding/OmenSuperHub), [OmenCore](https://github.com/theantipopau/omencore) and [Ohman](https://github.com/P4R1H/ohman) replace OMEN Gaming Hub.

## Uninstall

```sh
sudo rm /etc/udev/rules.d/99-omen-fan.rules
rm -r ~/.local/share/applications/omen-fan.desktop ~/.config/omen-fan
```

## Tests

```sh
python3 -m pytest
```

## License

MIT
