#!/usr/bin/env bash
# Prints what OMEN Fan Control needs to know about this laptop.
# Paste the output into a "Compatibility report" issue.
echo "Model:   $(cat /sys/class/dmi/id/product_name 2>/dev/null)"
echo "Board:   $(cat /sys/class/dmi/id/board_name 2>/dev/null)"
echo "Distro:  $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
echo "Kernel:  $(uname -r)"
hw=""
for d in /sys/class/hwmon/hwmon*; do
    [[ "$(cat "$d/name" 2>/dev/null)" == "hp" ]] && hw="$d"
done
if [[ -z "$hw" ]]; then
    echo "Result:  NOT SUPPORTED - no hp-wmi hwmon device (is the hp_wmi module loaded?)"
    exit 1
fi
echo "Fans:    $(ls "$hw" | grep -E '^fan[0-9]+_input$' | tr '\n' ' ')"
if [[ -e "$hw/pwm1_enable" ]]; then
    echo "Mode:    pwm1_enable=$(cat "$hw/pwm1_enable") (0=max, 2=auto)"
    echo "Result:  SUPPORTED"
else
    echo "Result:  NOT SUPPORTED - fan speeds are readable but there is no pwm1_enable"
    exit 1
fi
