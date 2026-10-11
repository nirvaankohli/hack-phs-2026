I'm building a hackathon project: a flappable cardboard-wings game controller.

HARDWARE
- Raspberry Pi 5 (Raspberry Pi OS, Python 3)
- Seeed Grove Base Hat for Raspberry Pi (full-size), on the 40-pin header
- Two Grove Rotary Angle Sensors (potentiometers), one per cardboard wing
  - Left wing → analog port A0, right wing → A2 (confirm with --raw mode)
- The Hat's ADC is an onboard MCU on I2C bus 1, address 0x08 (older Hats: 0x04).
  Register 0x10 + channel returns a 12-bit raw value (0–4095).

CONSTRAINTS
- Pi 5: do NOT use RPi.GPIO or Seeed's grove.py (they break on the Pi 5's RP1
  chip). Read the ADC with smbus2 directly, as wings_test.py already does.
- Install packages with: pip3 install <pkg> --break-system-packages
- You're running ON the Pi, and the Hat + both wing sensors are plugged in
  right now. Use the real Hat: run `python3 wings_test.py --raw` to confirm
  the wiring and `i2cdetect -y 1` if the Hat isn't found. When you need real
  input (calibration, tuning flap thresholds, testing the game), tell me
  exactly what to do with the wings and I'll do it.
- The game reads the Hat by default. If the Hat isn't found at startup, print
  a clear message and fall back to spacebar instead of crashing.
- Still keep the sensor layer mockable (a fake ADC class) so the flap logic
  can be unit-tested with simulated input and the game runs on my laptop.

CURRENT STATE
wings_test.py in this folder is working test firmware:
- --raw: prints all 4 analog ports
- --calibrate: records wings-down / wings-up, saves wings_cal.json
- default: live view, normalizes each wing to 0.0 (down)–1.0 (up), smooths
  with an EMA, and detects a "flap" as a fast downstroke (velocity +
  min travel + cooldown). Also computes tilt = right - left.
Read it first and keep its calibration format and flap logic.
Notes on the current code:
- A flap is detected on the AVERAGE of both wings (one flap event per
  stroke, not one per wing). Keep that, but also expose per-wing positions.
- It calls sys.exit() at import time if smbus2 is missing, so it can't be
  imported on a laptop. The new module must import cleanly without smbus2
  (needed for --mock).

WHAT I WANT NEXT
1. Refactor the sensor + flap detection into an importable module
   (e.g. wings.py) that exposes a simple API: a generator or callback that
   yields flap events and current positions/tilt. Keep wings_test.py working
   (it can become a thin CLI on top of wings.py).
2. Build a Flappy Bird–style game in pygame that runs on the Pi
   (fullscreen-capable, also playable with spacebar as a fallback) where each
   wing flap makes the bird jump. Bonus: harder flap (faster stroke) = bigger jump.
3. Add a --mock flag so the game can also run on my laptop without the Hat,
   using spacebar as fake flaps. (The default, with no flag, is the real Hat.)
4. When it's built, test it end to end on the real wings with me: calibrate,
   check that flaps register reliably (no misses, no double-triggers), and
   tune the thresholds if needed.
5. Keep it simple and hackathon-friendly: few files, a README with setup
   and run commands, no heavy dependencies beyond smbus2 and pygame.

Before writing code, read wings_test.py and tell me your plan in a few lines.
