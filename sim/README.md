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

## Fly with the wing

```
python tracking/wing_controller.py --sim
```

This serves the sim at http://localhost:8123, opens it, and streams the live
wing pose to it. It sends no key presses, so the page doesn't need focus. Hold
the wing level and press **F8** (or click START in the tracker window) to
calibrate. The eagle then copies your arms:

| Your wing                              | The eagle                                               |
| -------------------------------------- | ------------------------------------------------------- |
| Tilt                                   | Banks and turns                                         |
| Hold it higher or lower                | Flies at that angle: climbs, or dives and then tucks into a stoop |
| Move it up and down                    | Its wings follow your arms, stroke for stroke           |
| Push down fast                         | Downstroke: lift and thrust in proportion to your speed |

Steady flapping gains height and keeps a slow bird from stalling. Holding
still lets it glide. Tune how the arm motion maps to the bird in the `WING`
settings at the top of `js/input.js`.

## Keys

- **← →** / **A D**: bank
- **↑ ↓** / **W S**: tilt the flight angle up or down. Hold to keep tilting;
  the angle stays where you leave it. Press **I** to invert.
- **Space**: one full wingbeat; hold to keep flapping
- **C**: chase, wide, or eagle's-eye camera
- **T**: morning, midday, or golden hour
- **Q**: graphics quality: ultra low, low, medium, or high
- **V**: variometer beeps; **M**: mute; **R**: respawn; **Esc**: pause

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
| `js/input.js`       | Live wing stream (`/pose`), keyboard and gamepad           |
| `js/audio.js`       | Synthesized wind, wingbeats, splashes and vario            |

Open the browser console and use `window.sim` to inspect the flight state
while debugging.
