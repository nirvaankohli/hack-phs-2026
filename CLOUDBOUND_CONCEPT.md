# Cloudbound game concept

**Pitch:** Take a selfie, grow angel wings, and flap your way through a sky full of trouble. Dodge storm clouds, weave between birds, and chase golden feathers until you break through into the sunlight.

Cloudbound is a short, side-scrolling flying game inspired by the readable controls and quick retries of Flappy Bird. The main attraction is seeing **your actual face with animated angel wings**, then keeping that ridiculous little character airborne. The mood is playful, dreamy, and slightly chaotic. The theme is **Into the Skies**: every run feels like a journey from the rooftops into a bright world above the clouds.

## The theme and visual direction

Use a storybook sky with soft painted clouds, peach sunlight, pale blue air, lavender shadows, and warm gold accents. Give the face a thin cream outline so a photographic cutout feels intentional against the illustrated scenery. Two oversized white feathered wings sit behind the face; a tiny tilted halo floats above it.

The character is a magical sky traveler. There is no death or afterlife story. On a crash, the face spins into a soft cloud puff, the halo wobbles, and the results appear.

Keep the foreground crisp and the background quiet. Distant clouds can be fluffy and pale; dangerous storm clouds have dark violet bodies, sharp undersides, and little internal flashes. Players should immediately understand what can hit them. Gold feathers are collectible; the halo and decorative wings cannot collide.

**Title screen copy:** “Your face. A pair of wings. A very questionable flight plan.”

**Start button:** “Get your wings”

## What the player dodges

The main obstacle should be **storm-cloud gates**: upper and lower banks of dark cloud with a clear opening between them. These supply the familiar Flappy Bird rhythm while belonging naturally in the sky. Shape them as irregular cloud masses rather than rectangular pipes with cloud textures.

| Obstacle | How it behaves | What the player does | Scope |
| --- | --- | --- | --- |
| Storm-cloud gates | Paired cloud banks scroll left with an opening at a different height each time. | Flap or glide to line up with the gap. | First version |
| Bird formations | A small group of indigo birds crosses in a straight, predictable line. No sudden dives or chasing. | Pass above or below the flock. | First version, after gates work |
| Drifting kites | A bright kite gently bobs along a fixed path. Its short ribbon stays inside a clearly visible danger silhouette. | Time the crossing around its movement. | Later variety |
| Lightning curtains | A storm cloud marks a vertical lane with sparks, then briefly fires a bolt. | Wait outside the marked lane until it clears. | Stretch goal |

**Recommendation:** Build cloud gates and birds first. That is enough for a coherent game. Save lightning until the basic flying feels fair; moving targets and timed hazards together would make the first version harder to read and tune.

Do not fill the sky with unrelated hazards. Birds, weather, and kites give it a recognizable identity. Avoid invisible wind forces in the first version because they make the controls feel inconsistent.

## Your face becomes the character

1. Show a camera preview with a face guide and the instruction “Put your face in the frame.”
2. The player presses Capture. Crop the face and remove its background.
3. Show the finished face with wings and halo immediately. Offer Retake and “That’s me.”
4. Fit every cutout into the same character frame so different faces receive the same gameplay difficulty.
5. Keep that captured image for the whole session and across retries. The player should not need another selfie after every crash.

The wings animate through an upstroke, a strong downstroke, and a relaxed glide. Each flap produces a few tiny feathers. The face tilts gently upward on ascent and downward on descent; it should stay recognizable.

Use one fixed circular hitbox centered on the face, slightly smaller than its visible frame. Hair, ears, wings, halo, and feather particles are cosmetic. A wing grazing a cloud should feel like a narrow escape, not an unfair collision.

If cropping fails, keep the camera preview and offer a retry. If the camera is unavailable, offer a built-in face avatar so the game remains playable. Proposed session behavior: retain the cutout in memory and discard it when the player leaves or chooses a new face.

## How flying works

The avatar stays around the left quarter of the screen. The world moves from right to left. Gravity pulls the avatar down; each flap gives an upward impulse. Releasing the control allows a glide and then a fall. The camera does not follow every vertical movement.

**Baseline control:** Space, click, or tap to flap. One press produces one flap; holding the button does not repeatedly fire. This should be the first playable version and remain available for every demo.

**Recommended physical control:** If the existing wing tracker is part of the intended experience, a deliberate downward wing stroke should trigger the same flap action. Calibrate raised and lowered poses before the run, trigger once on the downstroke, and require a return toward the raised pose before another flap. Do not trigger continuously while the wings are held down. Start with a short debounce interval and tune it against actual tracker noise.

The captured face is the avatar, not a requirement to steer by moving your head. Head steering would introduce a different control scheme and is outside this concept’s first version.

When physical tracking is lost, pause gameplay and show “Wings out of view.” Resume with a countdown once tracking returns, or let the player switch to button controls. Do not turn a camera dropout into a crash.

## A complete run

Start with a **60-second flight to the golden sky**. A short finishable mode gives the player a destination and makes the project easy to demonstrate. The following timings are initial design targets to tune during playtesting.

| Time | Scene | Gameplay |
| --- | --- | --- |
| 0–10 seconds | Rooftops far below, bright morning air | Safe opening runway, one practice flap, then very wide cloud gates. |
| 10–25 seconds | Blue sky and scattered clouds | Gates shift between nearby heights; gold feathers show the intended flight path. |
| 25–45 seconds | Lavender storm belt | Gates become moderately tighter. Introduce birds in open stretches between gates. |
| 45–60 seconds | Peach light and golden cloud edges | A final sequence mixes familiar patterns, followed by an open finish arch. |

The journey upward is conveyed through scenery and checkpoints while the game keeps its simple horizontal scrolling. Avoid changing the camera direction mid-run.

After the finish arch, the wings stretch out into a glide and the player gets **“You earned your wings.”** Show their winged face, score, feathers collected, and best score. Offer Fly Again and New Face. Endless mode can follow after this complete run is polished.

On a crash, freeze briefly for impact feedback, play the cloud-puff animation, and show **“A little turbulence.”** Make retry one action, using the same face. A short restart countdown is enough; skip the original onboarding.

## Scoring and difficulty

- **10 points** for each cloud gate passed.
- **5 points** for each gold feather collected.
- **100 points** for finishing the flight.
- Keep a local best score. No accounts or online leaderboard in the first version.

Feathers should usually trace the safe route. A few optional feathers can sit near the edge of a gap for a modest risk and reward choice. Never require a collectible to survive or open the finish.

Use a small set of authored obstacle patterns for the first version. Begin with openings about four avatar diameters tall, then test a gradual reduction toward three. Leave enough distance between gates to recover from a poor flap. Never place birds inside the only safe opening, spawn a hazard on the player, or combine lightning with a required gate crossing.

Cap falling speed and keep the upper edge forgiving: reaching the ceiling gently stops ascent. Falling below the visible lower boundary ends the run, with a visible cloud-floor edge so the boundary is understandable.

## What is on screen

During a run, show the score in the upper left, a small route progress bar at the top, and pause and mute in the upper right. Keep the center clear for obstacles. In wing-control mode, add a small tracking indicator; a live webcam preview belongs in setup or debugging, not over the playfield.

Use a soft whoosh for a flap, a bright chime for a feather, and a gentle puff on collision. Increase musical energy through the storm belt and resolve it into a warm chord at the finish. Motion, outlines, and sounds should reinforce feedback without requiring sound or color alone to understand the game. Avoid rapid lightning flashes and screen shake.

## First version build scope

Build in this order:

1. **Flying feels good:** placeholder avatar, flap physics, cloud gates, collision, and instant retry.
2. **The player is the character:** capture, transparent face crop, preview, face sizing, and animated wings.
3. **The run has a destination:** authored 60-second route, changing scenery, feathers, score, and finish screen.
4. **The sky has life:** predictable bird formations, sound, particles, and a little face tilt.
5. **Physical wings control the flight:** connect and calibrate tracking if required for the demo, retaining button input as a fallback.

The first demo is complete when a new player can capture their face, understand one flap control, play a fair run, and retry without assistance. Test that different face shapes share the same hitbox, restarting resets the route and score, and tracking loss pauses safely when wing control is enabled.

Leave shops, multiplayer, power-ups, procedural difficulty, character inventories, and boss fights for later. The face reveal and satisfying flying should carry the demo.

## Fit with the current project

The inspected checkout contains `face/` and `tracking/`; a `game/` directory was not present when this concept was written.

- `face/api.py` already exposes `POST /crop`, which returns a transparent PNG. It can supply the avatar image after capture.
- `tracking/api.py` exposes `POST /track`, reporting whether five markers were found and returning wing measurements. A calibration and stroke-detection layer would still be needed to convert those measurements into flap events.
- The game needs the playable scene, input handling, physics, obstacle patterns, score, and the capture-to-retry flow described above.

**Demo pitch:** “Take a selfie and become the flying character. Your face gets angel wings, and you guide it through a storm to reach the golden sky.” If physical controls are working, add: “Flap the real wings to flap in the game.”
