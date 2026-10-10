# Icarus: Risk the Sun

A keyboard-first Godot 4 arcade game for HackPHS 2026's Into the Skies theme.
Import project.godot and press F5.

Climb toward sunlight for points. Above 65% altitude, heat builds and weakens
flap lift while adding sinking. Descend to cool slowly, or fly inside a cooling
cloud to restore fully overheated wings in three seconds. Maximum heat is
recoverable; hitting the sea ends the run. The upper boundary is safe.

- Space: one flap per press, with a 0.32-second cooldown.
- Up / Down: adjust wing angle; release retains the angle.
- Left / Right: level wings. Hot wings still sink.
- Enter / Space: start or retry. Escape: pause/resume. R: restart.

Scoring: 10 times normalized altitude squared per second. Reach 75% heat,
then cool to 25% inside a cloud for a 100-point recovery bonus. Another dangerous
climb is required for another bonus. Best score lasts for the current session.
There is no hard timer; cautious flying can continue indefinitely.

Visuals are drawn in Godot. Legacy Flappy Bird assets are unused.
Live tracking is deferred. set_flight_angle(degrees) accepts finite angles
clamped to -60 through 0; flight.flap(strength) remains a separate action.
The sibling tracking service supplies per-image wing measurements; camera
streaming, calibration, and temporal flap recognition are not connected.

Run tests from this directory:

```
godot --headless --path . --script res://tests/flight_test.gd
godot --headless --path . --script res://tests/icarus_test.gd
```
