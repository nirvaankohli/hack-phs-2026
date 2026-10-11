// Turns the player's wing (or keyboard / gamepad) into flight commands:
//   roll       -1..1  bank command
//   pitch      -1..1  flight-angle command (+ = nose up)
//   flapPower   0..1  how hard the wings are pushing down right now
//   stroke     -1..1  where the bird's wings sit in their beat (+ = raised)
//
// With `wing_controller.py --sim` the live wing pose streams in over /pose and
// the bird copies the arms directly: tilt banks, holding the wing up or down
// sets the flight angle, and the speed of each downstroke becomes lift.

const ROLL_LEFT = ['ArrowLeft', 'KeyA'];
const ROLL_RIGHT = ['ArrowRight', 'KeyD'];
const NOSE_UP = ['ArrowUp', 'KeyW'];
const NOSE_DOWN = ['ArrowDown', 'KeyS'];
const FLAP = ['Space', 'KeyF'];
const CAPTURED = new Set([...ROLL_LEFT, ...ROLL_RIGHT, ...NOSE_UP, ...NOSE_DOWN, ...FLAP]);
const ROLL_SMOOTHING = 0.16;   // seconds
const PITCH_RATE = 0.9;        // keyboard: full command range per ~2 s of holding
const GAMEPAD_DEADZONE = 0.08;
// One keyboard wingbeat: raise, power down, recover.
const BEAT = { raise: 0.1, down: 0.25, recover: 0.15 };
const BEAT_LENGTH = BEAT.raise + BEAT.down + BEAT.recover;

// Live wing tuning, in the same units wing_controller.py sends.
const WING = {
  maxRoll: 30,        // degrees of wing tilt for a full bank
  holdTime: 0.7,      // seconds: slower height changes count as holding a pitch
  pitchRange: 0.25,   // wingspans above/below neutral for a full pitch command
  strokeRange: 0.3,   // wingspans of quick motion drawn as a full wingbeat
  minDownstroke: 0.5, // wingspans per second before a downward motion counts as flapping
  fullDownstroke: 2.5,
};

const shape = (value, deadzone) =>
  Math.sign(value) * Math.min(1, Math.max(0, (Math.abs(value) - deadzone) / (1 - deadzone)));

class WingStream {
  constructor(url = '/pose') {
    this.url = url;
    this.connected = false;
    this.active = false;
    this.lastMessage = 0;
    this.roll = 0;
    this.lift = 0;
    this.held = 0;
    this.velocity = 0;
    this.previous = null;
    this.connect();
  }

  connect() {
    if (!window.EventSource) return;
    const source = new EventSource(this.url);
    source.onopen = () => { this.connected = true; };
    source.onmessage = (event) => this.receive(JSON.parse(event.data));
    source.onerror = () => {
      // A plain static server has no /pose; try again later in case the controller starts.
      if (!this.connected) {
        source.close();
        setTimeout(() => this.connect(), 8000);
      }
    };
  }

  receive(data) {
    this.lastMessage = performance.now();
    this.active = !!data.active;
    if (!this.active) {
      this.previous = null;
      this.velocity = 0;
      return;
    }
    if (this.previous) {
      const dt = data.t - this.previous.t;
      if (dt > 0 && dt < 0.25) {
        const v = (data.lift - this.previous.lift) / dt;
        this.velocity += (v - this.velocity) * 0.6;
        this.held += (data.lift - this.held) * (1 - Math.exp(-dt / WING.holdTime));
      }
    } else {
      this.held = data.lift;
    }
    this.previous = data;
    this.roll = data.roll;
    this.lift = data.lift;
  }

  get live() {
    return this.active && performance.now() - this.lastMessage < 500;
  }
}

export class Input {
  constructor() {
    this.keys = new Set();
    this.flapQueued = false;
    this.roll = 0;
    this.pitch = 0;
    this.flapPower = 0;
    this.stroke = 0;
    this.invertPitch = false;
    this.source = 'keyboard';
    this.beat = BEAT_LENGTH;
    this.wing = new WingStream();
    addEventListener('keydown', (e) => {
      if (CAPTURED.has(e.code)) e.preventDefault();
      this.keys.add(e.code);
      if (FLAP.includes(e.code) && !e.repeat) this.flapQueued = true;
    });
    addEventListener('keyup', (e) => this.keys.delete(e.code));
    // Never leave a key stuck down if focus leaves the page mid-press.
    addEventListener('blur', () => this.keys.clear());
  }

  any(codes) {
    return codes.some((code) => this.keys.has(code));
  }

  /** Puts the held pitch back to a level glide (after a respawn, say). */
  level() {
    this.pitch = 0;
  }

  update(dt) {
    if (this.wing.live) {
      this.fromWing();
      this.flapQueued = false;
      return;
    }
    const roll = this.any(ROLL_RIGHT) - this.any(ROLL_LEFT);
    let pitch = this.any(NOSE_UP) - this.any(NOSE_DOWN);
    if (this.invertPitch) pitch = -pitch;
    this.roll += (roll - this.roll) * (1 - Math.exp(-dt / ROLL_SMOOTHING));
    // Holding up/down keeps changing the flight angle; letting go keeps it.
    this.pitch = Math.min(1, Math.max(-1, this.pitch + pitch * PITCH_RATE * dt));
    if (roll || pitch) this.source = 'keyboard';

    // Each press is one full wingbeat; holding keeps beating.
    if ((this.flapQueued || this.any(FLAP)) && this.beat >= BEAT_LENGTH) this.beat = 0;
    this.flapQueued = false;
    this.beat = Math.min(BEAT_LENGTH, this.beat + dt);
    this.keyboardBeat();

    for (const pad of navigator.getGamepads ? navigator.getGamepads() : []) {
      if (!pad) continue;
      const [x = 0, y = 0] = pad.axes;
      const pressed = !!pad.buttons[0]?.pressed;
      if (Math.abs(x) > GAMEPAD_DEADZONE || Math.abs(y) > GAMEPAD_DEADZONE || pressed) {
        // Stick back (positive Y) is nose up, as wing_controller.py --gamepad sends it.
        this.roll = Math.abs(x) > GAMEPAD_DEADZONE ? x : 0;
        this.pitch = Math.abs(y) > GAMEPAD_DEADZONE ? (this.invertPitch ? -y : y) : 0;
        this.source = 'gamepad';
      }
      if (pressed && this.beat >= BEAT_LENGTH) this.beat = 0;
      break;
    }
  }

  keyboardBeat() {
    const t = this.beat;
    if (t < BEAT.raise) {
      this.stroke = (t / BEAT.raise) * 0.9;
      this.flapPower = 0;
    } else if (t < BEAT.raise + BEAT.down) {
      const k = (t - BEAT.raise) / BEAT.down;
      this.stroke = 0.9 - 1.9 * k;
      this.flapPower = 1;
    } else if (t < BEAT_LENGTH) {
      this.stroke = -1 + (t - BEAT.raise - BEAT.down) / BEAT.recover;
      this.flapPower = 0;
    } else {
      this.stroke = 0;
      this.flapPower = 0;
    }
  }

  fromWing() {
    const w = this.wing;
    this.source = 'wing';
    this.roll = shape(w.roll / WING.maxRoll, 0.08);
    let pitch = shape(w.held / WING.pitchRange, 0.12);
    if (this.invertPitch) pitch = -pitch;
    this.pitch = pitch;
    // The bird's wings sit where the arms are, relative to the held position.
    this.stroke = Math.max(-1, Math.min(1, (w.lift - w.held) / WING.strokeRange));
    this.flapPower = Math.min(1, Math.max(0,
      (-w.velocity - WING.minDownstroke) / (WING.fullDownstroke - WING.minDownstroke)));
  }
}
