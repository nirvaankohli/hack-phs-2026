# hack-phs-2026

See [tracking/README.md](tracking/README.md) for the lightweight Python webcam
tracker: five colored wing markers, live connecting lines, position measurements,
and editable hex colors.

## Wing controller

`tracking/wing_controller.py` turns the wing into arrow-key input for flight
games such as GeoFS or YSFlight: tilt to bank, raise/lower to pitch. Click
**START** (3-second countdown) or press **F8** with the wing level to
calibrate and start; again to pause. Input is released whenever a dot is lost.
Use one purple dot on each wingtip, or `--dots 5` for the full 5-dot wing.

```
pip install -r tracking/requirements.txt
python tracking/wing_controller.py                        # GeoFS
python tracking/wing_controller.py --hotkey f11 --split   # YSFlight (uses F8 itself), side by side
```
