#!/usr/bin/env python3
"""
Cardboard Wings Controller - test firmware for Raspberry Pi 5 + Grove Base Hat.

Each wing turns a Grove Rotary Angle Sensor (potentiometer) plugged into an
analog port on the Grove Base Hat. This script reads the Hat's ADC over I2C
and detects "flaps" (a fast downstroke).

Modes:
  python3 wings_test.py --raw          # print all 4 analog ports (find your wiring)
  python3 wings_test.py --calibrate    # record wings-down / wings-up positions
  python3 wings_test.py                # live view + flap detection

Setup (once):
  sudo raspi-config  -> Interface Options -> I2C -> Enable
  pip3 install smbus2 --break-system-packages
  i2cdetect -y 1     # Hat should show up at 0x08 (or 0x04 on older Hats)
"""

import argparse
import json
import os
import sys
import time

try:
    from smbus2 import SMBus
except ImportError:
    sys.exit("Missing smbus2. Run: pip3 install smbus2 --break-system-packages")

# ---- Config ---------------------------------------------------------------

I2C_BUS = 1
HAT_ADDRESSES = (0x08, 0x04)   # STM32 Hat, then older MM32 Hat
REG_RAW = 0x10                 # 0x10 + channel -> 12-bit raw value (0-4095)
PORTS = {"A0": 0, "A2": 2, "A4": 4, "A6": 6}

LEFT_PORT = "A0"               # change to match where each wing is plugged in
RIGHT_PORT = "A2"

SAMPLE_HZ = 100
SMOOTHING = 0.35               # EMA factor: higher = more responsive, noisier
FLAP_SPEED = 2.5               # downstroke speed (full-range per second) to count as a flap
FLAP_MIN_TRAVEL = 0.25         # wing must have moved at least this far down
FLAP_COOLDOWN = 0.25           # seconds before another flap can register

CAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wings_cal.json")


# ---- Hardware -------------------------------------------------------------

class GroveADC:
    def __init__(self, bus=I2C_BUS):
        self.bus = SMBus(bus)
        self.addr = None
        for addr in HAT_ADDRESSES:
            try:
                self.bus.read_word_data(addr, REG_RAW)
                self.addr = addr
                break
            except OSError:
                continue
        if self.addr is None:
            sys.exit(
                "Grove Base Hat not found on I2C bus 1.\n"
                "Check: I2C enabled in raspi-config, Hat seated on all 40 pins, "
                "and `i2cdetect -y 1` shows 0x08 or 0x04."
            )

    def read_raw(self, channel):
        return self.bus.read_word_data(self.addr, REG_RAW + channel) & 0x0FFF


# ---- Calibration ----------------------------------------------------------

def sample_avg(adc, channel, seconds=1.0):
    vals = []
    end = time.time() + seconds
    while time.time() < end:
        vals.append(adc.read_raw(channel))
        time.sleep(1 / SAMPLE_HZ)
    return sum(vals) / len(vals)


def calibrate(adc):
    l, r = PORTS[LEFT_PORT], PORTS[RIGHT_PORT]
    input("Hold BOTH wings all the way DOWN, then press Enter...")
    down = (sample_avg(adc, l), sample_avg(adc, r))
    input("Hold BOTH wings all the way UP, then press Enter...")
    up = (sample_avg(adc, l), sample_avg(adc, r))

    cal = {
        "left": {"down": down[0], "up": up[0]},
        "right": {"down": down[1], "up": up[1]},
    }
    for side, c in cal.items():
        span = abs(c["up"] - c["down"])
        if span < 200:
            print(f"Warning: {side} wing only moves {span:.0f}/4095 counts. "
                  "Check the sensor is plugged in and the shaft actually turns.")
    with open(CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2)
    print(f"Saved calibration to {CAL_FILE}")
    return cal


def load_cal():
    if not os.path.exists(CAL_FILE):
        return None
    with open(CAL_FILE) as f:
        return json.load(f)


def normalize(raw, c):
    """0.0 = wing down, 1.0 = wing up. Works even if a sensor is mounted reversed."""
    span = c["up"] - c["down"]
    if abs(span) < 1:
        return 0.0
    return max(0.0, min(1.0, (raw - c["down"]) / span))


# ---- Flap detection -------------------------------------------------------

class Wing:
    def __init__(self, cal):
        self.cal = cal
        self.pos = None
        self.vel = 0.0
        self.peak = 0.0        # highest point since last flap

    def update(self, raw, dt):
        target = normalize(raw, self.cal)
        if self.pos is None:
            self.pos = self.peak = target
            return
        new = self.pos + SMOOTHING * (target - self.pos)
        self.vel = (new - self.pos) / dt
        self.pos = new
        self.peak = max(self.peak, self.pos)


def bar(v, width=20):
    n = int(round(v * width))
    return "█" * n + "·" * (width - n)


# ---- Modes ----------------------------------------------------------------

def run_raw(adc):
    print("Raw readings (0-4095). Turn each wing to see which port it's on. Ctrl+C to stop.\n")
    while True:
        vals = {name: adc.read_raw(ch) for name, ch in PORTS.items()}
        print("  ".join(f"{k}:{v:4d}" for k, v in vals.items()), end="\r", flush=True)
        time.sleep(0.05)


def run_live(adc, cal):
    left, right = Wing(cal["left"]), Wing(cal["right"])
    l_ch, r_ch = PORTS[LEFT_PORT], PORTS[RIGHT_PORT]
    flaps, last_flap = 0, 0.0
    last = time.time()
    print("Flap away! Ctrl+C to stop.\n")

    while True:
        now = time.time()
        dt = max(now - last, 1e-3)
        last = now

        left.update(adc.read_raw(l_ch), dt)
        right.update(adc.read_raw(r_ch), dt)

        avg_pos = (left.pos + right.pos) / 2
        avg_vel = (left.vel + right.vel) / 2
        peak = (left.peak + right.peak) / 2
        tilt = right.pos - left.pos   # + = right wing higher (for steering later)

        event = ""
        if (avg_vel < -FLAP_SPEED
                and peak - avg_pos >= FLAP_MIN_TRAVEL
                and now - last_flap > FLAP_COOLDOWN):
            flaps += 1
            last_flap = now
            left.peak, right.peak = left.pos, right.pos
            event = f"  >>> FLAP #{flaps}"
            print()  # keep the flap line visible

        # let the peak follow the wing back up after a flap
        if avg_vel > 0:
            left.peak = max(left.peak, left.pos)
            right.peak = max(right.peak, right.pos)

        print(f"L {bar(left.pos)} {left.pos:4.2f}  "
              f"R {bar(right.pos)} {right.pos:4.2f}  "
              f"vel {avg_vel:+5.1f}  tilt {tilt:+4.2f}{event}   ",
              end="\n" if event else "\r", flush=True)

        time.sleep(max(0, 1 / SAMPLE_HZ - (time.time() - now)))


def main():
    p = argparse.ArgumentParser(description="Cardboard wings controller test")
    p.add_argument("--raw", action="store_true", help="print raw ADC values on all ports")
    p.add_argument("--calibrate", action="store_true", help="record down/up positions")
    args = p.parse_args()

    adc = GroveADC()
    print(f"Grove Base Hat found at 0x{adc.addr:02X}")

    try:
        if args.raw:
            run_raw(adc)
        cal = calibrate(adc) if args.calibrate else load_cal()
        if cal is None:
            print("No calibration found, running it now.")
            cal = calibrate(adc)
        run_live(adc, cal)
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
