#!/usr/bin/env bash
# One-time setup: let members of the "sudo" group change the fan mode without
# a password prompt, and add an app-menu entry.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
RULE=/etc/udev/rules.d/99-omen-fan.rules

sudo tee "$RULE" >/dev/null <<'EOF'
# HP OMEN fan mode (hp-wmi): allow the sudo group to write pwm1_enable
ACTION=="add", SUBSYSTEM=="hwmon", ATTR{name}=="hp", RUN+="/bin/chgrp sudo /sys%p/pwm1_enable", RUN+="/bin/chmod g+w /sys%p/pwm1_enable"
EOF
sudo udevadm control --reload-rules

# Apply now, without waiting for a reboot.
for hw in /sys/class/hwmon/hwmon*; do
    if [[ "$(cat "$hw/name" 2>/dev/null)" == "hp" && -e "$hw/pwm1_enable" ]]; then
        sudo chgrp sudo "$hw/pwm1_enable"
        sudo chmod g+w "$hw/pwm1_enable"
    fi
done

chmod +x "$DIR/omen_fan_gui.py"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/omen-fan.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OMEN Fan Control
Comment=Switch laptop fans between Auto, Smart and Max
Exec=python3 $DIR/omen_fan_gui.py
Icon=weather-windy
Categories=System;Settings;
Terminal=false
EOF

echo "Installed. Launch 'OMEN Fan Control' from the app menu or run: python3 $DIR/omen_fan_gui.py"
