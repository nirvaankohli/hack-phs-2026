# hack-phs-2026

See [tracking/README.md](tracking/README.md) for the lightweight Python webcam
tracker: five colored wing markers, live connecting lines, position measurements,
and editable hex colors.

## Cloudbound game

Open [`game/project.godot`](game/project.godot) in Godot 4, or double-click
[`game/launch.command`](game/launch.command) on macOS to launch the game and local
camera bridge together. See [`game/README.md`](game/README.md) for keyboard controls,
physical-wing calibration, API integration, and verification commands.

## Wing controller

`tracking/wing_controller.py` turns the wing into arrow-key input for flight
games such as GeoFS or YSFlight: tilt to bank, raise/lower to pitch. Click
**START** (3-second countdown) or press **F8** with the wing level to
calibrate and start; again to pause. Input is released whenever a dot is lost.
Use one purple dot on each wingtip, `--dots 3` to add one in the middle (the default with `--sim`), or `--dots 5` for the full 5-dot wing.

```
pip install -r tracking/requirements.txt
python tracking/wing_controller.py                        # GeoFS
python tracking/wing_controller.py --hotkey f11 --split   # YSFlight (uses F8 itself), side by side
```

Add `--voice` for ElevenLabs callouts (countdown, "Pull up!", steep bank,
lost tracking, and a spoken flight summary on pause). Set your API key in the
same PowerShell window first: `$env:ELEVENLABS_API_KEY = "your key"`. Lines are
cached in `tracking/voice_cache/` after the first time they play.

## Skyborne: be a bird

[sim/](sim/README.md) is a 3D browser sim where you fly as a bald eagle. You
can ride thermals, stoop into dives and perch on the ground. With the wing
controller, the eagle copies your arms: tilt to bank, hold high or low to set
the flight angle, and beat down to flap and gain height.

```
.venv\Scripts\python sim\server.py                    # camera wings via the Cloudbound bridge; press K to calibrate
python tracking/wing_controller.py --sim              # cardboard wing alternative; press F8
python -m http.server 8123 --directory sim            # keyboard only, then open http://localhost:8123
```
