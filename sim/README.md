# Skyborne

A browser flight sim where you are a bald eagle over an endless coast of
beaches, forests and snow-capped ridges. It is built to be flown with the
cardboard wing and `tracking/wing_controller.py`, and also works with a
keyboard or gamepad.

## Run it

```
python -m http.server 8123 --directory sim
```

Open http://localhost:8123 in Chrome or Edge. Three.js loads from a CDN, so
the first run needs internet. Press **Q** in the sim to cycle graphics quality.
The choice is remembered, and a `?quality=ultra` (or `low`, `medium`, `high`)
URL parameter overrides it. If the first seconds of flight run slowly, the sim
suggests pressing Q.

| Level     | For                                    | What changes                                       |
| --------- | -------------------------------------- | -------------------------------------------------- |
| Ultra low | 8 GB laptops with integrated graphics  | 60% resolution, no trees or shadows, coarse terrain, 1.6 km view, half the cloud puffs, no antialiasing |
| Low       | Older or weaker GPUs                   | No shadows, trees only nearby, 2.4 km view         |
| Medium    | Most computers (default)               | Shadows, 3.2 km view                               |
| High      | Strong GPUs                            | Sharper image on high-DPI screens, 3.6 km view     |

Antialiasing is set when the page loads. To get the full Ultra low speedup,
switch to it and reload, or open http://localhost:8123/?quality=ultra.

## Fly with your arms (camera bridge)

Skyborne uses Cloudbound's camera bridge (`game/bridge.py`). Wear a marker on
each wing and one on your body between them, all the same color. Run from the
repository root:

```
.venv\Scripts\python sim\server.py
```

This serves the sim at http://localhost:8123 and opens it. The webcam turns on
as soon as the page opens, so it's ready by the time you press Space. On
Windows the server opens it with DirectShow, which takes about 2 s instead of
the 5–10 s of OpenCV's default driver. Spread your wings level and press **K**
to calibrate after a 3-second countdown. The webcam turns off when you close
the tab.

A live camera view sits in the bottom-right corner, with the tracked markers
circled, the marker count and the tracking status. Press **L** to switch it to
marker view, which dims everything except the marker color so you can check
the color settings. Press **L** again to hide it.

The marker settings are built in, from Cloudbound's Wing color sliders:

| Setting          | Value                                     |
| ---------------- | ----------------------------------------- |
| Color            | `#C45C75` (hue 346, saturation 53, brightness 77) |
| Hue tolerance    | 8                                         |
| Shade tolerance  | 114                                       |
| Minimum dot size | 1 px²                                     |

Override them with `--color`, `--hue-tolerance`, `--shade-tolerance` and
`--min-dot-area`.

Lips, skin and headwear can match a reddish marker color. Skyborne finds your
face with the repository's MediaPipe model and ignores matches on your face,
around your mouth, and on a turban, hat or hair above it. The live camera view
outlines that area in orange. It also ignores blobs bigger than 4000 px², which
no marker should be. Change the limit with `--max-dot-area`, or turn the head
filter off with `--keep-head`. This lives in `sim/markers.py`; Cloudbound's
own tracking is unchanged. Use `?camera=1` in the address for another webcam.

| Your arms                        | The eagle                                          |
| -------------------------------- | -------------------------------------------------- |
| One wing up, the other down      | Banks and turns                                    |
| Both held higher or lower        | Flies at that angle, climbing or diving            |
| Bend both arms in toward your body | Tucks into a steep stoop                         |
| Move them                        | Each wing follows its own arm, stroke for stroke   |
| Push down fast                   | Downstroke: lift and thrust, stronger the faster you push |

Wing heights are measured from the body marker, so walking or bobbing doesn't
count as flapping. The flight angle only follows arms held still. While you
flap, the angle holds and tucks are ignored, so each downstroke lifts you
instead of dipping into a dive. A tuck is judged by arm reach (body marker to
wing marker), so swinging your arms down to flap never counts as folding them. If a marker drops out, the sim shows "Wing lost" with the
marker count, and the eagle glides until all three are back. Tune the arm
mapping in `WING` at the top of `js/input.js`.

`tracking/wing_controller.py --sim` still works as an alternative for the
cardboard wing with three purple dots, using F8 to calibrate.

## Keys

- **← →** / **A D**: bank
- **↑ ↓** / **W S**: tilt the flight angle up or down. Hold to keep tilting;
  the angle stays where you leave it. Press **I** to invert.
- **Space**: one full wingbeat; hold to keep flapping
- **G**: altitude graph on or off
- **C**: chase, wide, or eagle's-eye camera
- **T**: morning, midday, or golden hour
- **Q**: graphics quality: ultra low, low, medium, or high
- **K**: calibrate the camera wings; **L**: live camera, marker view, or off (with `server.py`)
- **V**: variometer beeps; **M**: mute; **R**: respawn; **Esc**: pause

## Altitude graph

The top-right panel plots the last 60 seconds. The gold line is your altitude
and the green profile is the ground you passed over, so the gap between them is
your clearance. The header shows your peak in that window and how much you've
climbed or dropped in the last 10 seconds. Press **G** to hide it.

## How the flying works

- **Gliding.** Hands-off, the eagle glides at about 17:1 and loses height
  slowly. Pulling up trades speed for height. Below about 30 km/h it stalls
  and the nose drops.
- **Turning.** The wing's tilt sets the bank angle, and bank sets the turn
  rate, as in a coordinated turn. Steep turns cost more energy.
- **Thermals.** Columns of rising air sit under the cumulus clouds, mostly
  over land. Hawks circle in the nearby ones. The climb meter turns green and
  the vario beeps faster as you climb. Circle tightly to stay inside.
- **Ridge lift.** Wind from the west rises up windward slopes. Behind a ridge
  the air sinks.
- **Flapping.** Each downstroke adds lift and thrust in proportion to how
  hard the wings push down. Steady flapping climbs at about 2–4 m/s. It uses
  stamina, and gliding restores it.
- **Landing.** Touch down on land slowly and shallowly to perch. Flap to take
  off. Hitting the sea or landing too fast respawns you at your last safe
  height.

## Code

| File                | What it does                                               |
| ------------------- | ---------------------------------------------------------- |
| `js/main.js`        | Renderer, camera modes, HUD, hawks, effects, main loop     |
| `js/flight.js`      | Flight model: bank and glide targets, energy, drag, flaps, landing |
| `js/world.js`       | Terrain height and colors, wind, thermals, ridge lift      |
| `js/terrain.js`     | Streams 400 m chunks at three levels of detail, plus instanced trees |
| `js/environment.js` | Atmospheric sky, image-based lighting, sun shadows, ocean, haze |
| `js/clouds.js`      | Instanced billboard cumulus, sorted back to front          |
| `js/bird.js`        | Procedural eagle with jointed, animated wings              |
| `server.py`         | Serves the sim on the Cloudbound camera bridge and streams `/pose` |
| `js/altgraph.js`    | Live altitude-over-time graph in the HUD                   |
| `js/input.js`       | Live wing stream (`/pose`), keyboard and gamepad           |
| `js/audio.js`       | Synthesized wind, wingbeats, splashes and vario            |

Open the browser console and use `window.sim` to inspect the flight state
while debugging.
