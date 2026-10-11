#!/usr/bin/env python3
"""
read_test.py - check that the rotary angle sensors on A0 and A2 are being read.

Turn each knob: its number should sweep roughly 0-4095 and its bar should move.

  sudo raspi-config nonint do_i2c 0           # enable I2C (once)
  pip3 install smbus2 --break-system-packages
  python3 read_test.py
"""

import sys
import time

from smbus2 import SMBus

PORTS = {"A0 (left)": 0, "A2 (right)": 2}
REG_RAW = 0x10  # 0x10 + channel -> 12-bit raw value


def find_hat(bus):
    for addr in (0x08, 0x04):
        try:
            bus.read_word_data(addr, REG_RAW)
            return addr
        except OSError:
            pass
    sys.exit("Grove Base Hat not found. Check it's seated on all 40 pins and run: i2cdetect -y 1")


def bar(raw, width=30):
    n = round(raw / 4095 * width)
    return "#" * n + "-" * (width - n)


def main():
    try:
        bus = SMBus(1)
    except FileNotFoundError:
        sys.exit("I2C is off. Run: sudo raspi-config nonint do_i2c 0   then reboot")

    addr = find_hat(bus)
    print(f"Hat found at 0x{addr:02X}. Turn the knobs. Ctrl+C to stop.\n")

    try:
        while True:
            parts = []
            for name, ch in PORTS.items():
                raw = bus.read_word_data(addr, REG_RAW + ch) & 0x0FFF
                parts.append(f"{name}: {raw:4d} [{bar(raw)}]")
            print("   ".join(parts), end="\r", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDone.")


if __name__ == "__main__":
    main()
