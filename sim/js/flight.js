// Soaring-bird flight model. The wing pose sets a target bank and flight angle
// (like a real bird shaping its wings), gravity trades height for speed, drag
// bleeds it off, and every downstroke pushes the bird up and forward in
// proportion to how hard the wings are driven down.

import * as THREE from 'three';
import { clamp, lerp, smoothstep } from './noise.js';
import { WIND, heightAt, liftAt } from './world.js';

const G = 9.81;
const MAX_BANK = 0.95;       // rad, about 55 degrees
const GLIDE = -0.06;         // rad: hands-off glide slope (about 17:1)
const MAX_CLIMB = 0.6;
const MAX_DIVE = 1.15;
const STALL = 8;             // m/s
const PARASITE = 0.0022;
const INDUCED = 40;

export class Flight {
  constructor() {
    this.position = new THREE.Vector3();
    this.velocity = new THREE.Vector3();
    this.lastSafe = new THREE.Vector3();
    this.reset(new THREE.Vector3(0, 200, 0), 0);
  }

  reset(position, heading) {
    this.position.copy(position);
    this.lastSafe.copy(position);
    this.heading = heading;
    this.speed = 16;
    this.gamma = 0;
    this.bank = 0;
    this.tuck = 0;
    this.flapping = false;
    this.flapPower = 0;
    this.flapStrength = 0;
    this.effort = 0;
    this.climbBoost = 0;
    this.stamina = 1;
    this.state = 'flying';
    this.stateTime = 0;
    this.vario = 0;
    this.lift = 0;
    this.air = { thermal: Infinity, ridge: 0 };
    this.crashedInWater = false;
    this.safeTimer = 0;
    this.flaps = 0;
    this.maxAltitude = position.y;
    this.distance = 0;
  }

  /** Returns 'flap' when a downstroke starts, so sound can react. */
  update(dt, input, time) {
    this.stateTime += dt;
    let event = null;
    if (this.state === 'crashed') {
      if (this.stateTime > 2.6) this.respawn();
      return event;
    }
    if (this.state === 'landed') {
      this.stamina = Math.min(1, this.stamina + dt * 0.25);
      if (input.flapPower > 0.3 && this.stateTime > 0.5) {
        this.state = 'flying';
        this.stateTime = 0;
        this.speed = 8;
        this.gamma = 0.45;
        this.climbBoost = 3.5;
        this.position.y += 0.4;
        this.flaps += 1;
        this.flapStrength = 1;
        event = 'flap';
      }
      return event;
    }

    const authority = smoothstep(3, 11, this.speed);
    this.bank += (input.roll * MAX_BANK - this.bank) * (1 - Math.exp(-dt * (0.8 + 2.6 * authority)));
    this.tuck += (smoothstep(-0.55, -0.95, input.pitch) - this.tuck) * (1 - Math.exp(-dt * 4));
    let target = input.pitch >= 0 ? lerp(GLIDE, MAX_CLIMB, input.pitch) : lerp(GLIDE, -MAX_DIVE, -input.pitch);
    // Steady flapping keeps a slow bird airborne, the way birds take off and hover.
    const stall = (1 - smoothstep(STALL - 2, STALL + 1.5, this.speed)) * (1 - clamp(this.effort * 4, 0, 1));
    // Without airspeed the wings can't hold the nose up.
    target = lerp(target, -0.7, stall);
    this.gamma += (target - this.gamma) * (1 - Math.exp(-dt * (0.6 + 1.6 * authority)));
    this.stall = stall;

    // Downstrokes: tucked wings can't flap, and tired wings push less.
    const power = (this.tuck < 0.5 ? input.flapPower : 0) * (0.45 + 0.55 * this.stamina);
    if (!this.flapping && power > 0.3) {
      this.flapping = true;
      this.flaps += 1;
      this.flapStrength = power;
      event = 'flap';
    } else if (this.flapping && power < 0.05) {
      this.flapping = false;
    }
    this.flapPower = power;
    this.effort += (power - this.effort) * (1 - Math.exp(-dt * 1.5));
    this.stamina = power > 0.05
      ? Math.max(0, this.stamina - input.flapPower * dt * 0.06)
      : Math.min(1, this.stamina + dt * 0.07);

    const load = 1 / Math.cos(this.bank);
    const drag = lerp(PARASITE, 0.0009, this.tuck) * this.speed ** 2
      + INDUCED * load * load / Math.max(this.speed, 4) ** 2 * (1 - this.tuck * 0.6);
    const thrust = 4.5 * power;
    this.speed = clamp(this.speed + (-G * Math.sin(this.gamma) - drag + thrust) * dt, 2, 75);
    // Lift beyond the bird's weight while the wings drive down; it fades between beats.
    this.climbBoost = (this.climbBoost + 9 * power * dt) * Math.exp(-dt * 1.5);

    // Coordinated turn: bank angle sets the turn rate.
    this.heading -= G * Math.tan(this.bank) / Math.max(this.speed, 6) * dt;

    const ground = Math.max(heightAt(this.position.x, this.position.z), 0);
    this.lift = liftAt(this.position.x, this.position.y, this.position.z, ground, time, this.air);
    const cosG = Math.cos(this.gamma);
    this.velocity.set(
      -Math.sin(this.heading) * cosG * this.speed + WIND.x,
      Math.sin(this.gamma) * this.speed + this.lift + this.climbBoost,
      -Math.cos(this.heading) * cosG * this.speed + WIND.z,
    );
    this.position.addScaledVector(this.velocity, dt);
    this.vario += (this.velocity.y - this.vario) * (1 - Math.exp(-dt * 2.5));
    this.distance += this.speed * dt;
    this.maxAltitude = Math.max(this.maxAltitude, this.position.y);

    const floor = Math.max(heightAt(this.position.x, this.position.z), 0);
    this.altitude = this.position.y - floor;
    this.safeTimer += dt;
    if (this.altitude > 40 && this.safeTimer > 2) {
      this.safeTimer = 0;
      this.lastSafe.copy(this.position);
    }
    if (this.position.y < floor + 0.3) {
      const water = floor <= 0.01;
      if (!water && this.speed < 15 && this.gamma > -0.4) {
        this.state = 'landed';
        this.speed = 0;
        this.gamma = 0;
        this.bank = 0;
        this.tuck = 0;
        this.position.y = floor;
      } else {
        this.state = 'crashed';
        this.crashedInWater = water;
        this.position.y = floor;
        event = water ? 'splash' : 'crash';
      }
      this.stateTime = 0;
    }
    return event;
  }

  respawn() {
    const p = this.lastSafe.clone();
    p.y = Math.max(p.y, Math.max(heightAt(p.x, p.z), 0) + 120);
    const heading = this.heading;
    const { flaps, distance, maxAltitude } = this;
    this.reset(p, heading);
    Object.assign(this, { flaps, distance, maxAltitude });
  }

  forward(target = new THREE.Vector3()) {
    const c = Math.cos(this.gamma);
    return target.set(-Math.sin(this.heading) * c, Math.sin(this.gamma), -Math.cos(this.heading) * c);
  }
}
