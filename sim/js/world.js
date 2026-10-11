// The landscape and the air above it: terrain height, ground colors, wind,
// thermals and ridge lift. Units are meters; Y is up; sea level is 0.

import { clamp, fbm, lerp, mulberry32, simplex2, smoothstep } from './noise.js';

const warpNoise = simplex2(11);
const continentNoise = simplex2(23);
const ridgeNoise = simplex2(37);
const hillNoise = simplex2(41);
const forestNoise = simplex2(53);
const colorNoise = simplex2(67);

export function heightAt(x, z) {
  // Domain warping bends coastlines and ridges so they don't look like noise.
  const wx = x + 350 * warpNoise(x * 0.0005, z * 0.0005);
  const wz = z + 350 * warpNoise(x * 0.0005 + 57.1, z * 0.0005 - 33.7);
  const land = fbm(continentNoise, wx * 0.00016, wz * 0.00016, 4) + 0.1;
  // Ridged multifractal: each octave is weighted by the one before, so detail
  // gathers on the ridges and valleys stay smooth.
  let ridge = 0;
  let amp = 1;
  let weight = 1;
  let fx = wx * 0.00055;
  let fz = wz * 0.00055;
  for (let i = 0; i < 6; i++) {
    let r = 1 - Math.abs(ridgeNoise(fx, fz));
    r *= r * weight;
    weight = clamp(r * 1.6, 0, 1);
    ridge += r * amp;
    amp *= 0.45;
    fx *= 2.05;
    fz *= 2.05;
  }
  const range = 0.55 + 0.45 * hillNoise(wx * 0.00009 + 7.3, wz * 0.00009 - 2.1);
  const mountains = smoothstep(0.06, 0.55, land) * range;
  const hills = fbm(hillNoise, x * 0.003, z * 0.003, 3);
  return land * 180 + mountains * ridge * 390 + hills * 20 * smoothstep(-0.02, 0.12, land);
}

/** 0..1 tree density. */
export function forestAt(x, z, h) {
  return smoothstep(0.02, 0.32, fbm(forestNoise, x * 0.0018, z * 0.0018, 3))
    * (1 - smoothstep(250, 340, h)) * smoothstep(4, 12, h);
}

const SAND = [0.80, 0.73, 0.55];
const WET_SAND = [0.52, 0.48, 0.36];
const SEABED = [0.16, 0.22, 0.21];
const MEADOW = [0.33, 0.43, 0.17];
const DRY = [0.53, 0.50, 0.29];
const FOREST_FLOOR = [0.11, 0.19, 0.08];
const TUNDRA = [0.45, 0.43, 0.35];
const ROCK = [0.53, 0.5, 0.46];
const SNOW = [0.93, 0.95, 0.98];

function mix(out, c, t) {
  out[0] = lerp(out[0], c[0], t);
  out[1] = lerp(out[1], c[1], t);
  out[2] = lerp(out[2], c[2], t);
}

/** Writes an sRGB ground color into `out` for a point with height h and normal Y ny. */
export function groundColor(x, z, h, ny, out) {
  const n = colorNoise(x * 0.01, z * 0.01) * 0.5 + colorNoise(x * 0.07, z * 0.07) * 0.25;
  if (h < 2.5 + n * 2) {
    out[0] = SAND[0]; out[1] = SAND[1]; out[2] = SAND[2];
    mix(out, WET_SAND, smoothstep(1.5, -0.5, h));
    mix(out, SEABED, smoothstep(-1, -30, h));
    return out;
  }
  out[0] = MEADOW[0]; out[1] = MEADOW[1]; out[2] = MEADOW[2];
  mix(out, DRY, clamp(0.5 + n, 0, 1));
  mix(out, FOREST_FLOOR, forestAt(x, z, h));
  mix(out, TUNDRA, smoothstep(260, 420, h + n * 40));
  const rock = smoothstep(0.86, 0.7, ny);
  mix(out, ROCK, rock);
  out[0] *= 1 + n * 0.15 * rock; out[1] *= 1 + n * 0.15 * rock; out[2] *= 1 + n * 0.15 * rock;
  mix(out, SNOW, smoothstep(430, 480, h + n * 60) * smoothstep(0.6, 0.78, ny));
  return out;
}

// ---- Air ---------------------------------------------------------------

export const WIND = { x: 3.2, z: 1.1 };  // m/s, a light westerly
export const TILE = 9000;               // thermals and clouds repeat every TILE meters

/** Wraps a coordinate into the tile copy nearest `center`. */
export function wrapNear(value, center) {
  return center + ((((value - center + TILE / 2) % TILE) + TILE) % TILE) - TILE / 2;
}

export const thermals = (() => {
  const random = mulberry32(7);
  const list = [];
  for (let i = 0; i < 42; i++) {
    list.push({
      x: random() * TILE,
      z: random() * TILE,
      radius: 70 + random() * 80,
      strength: 2.4 + random() * 2.6,
      base: 560 + random() * 140,  // cloud base: lift fades out here
    });
  }
  return list;
})();

/** Thermal positions drift with the wind; this is how far they've moved. */
export function drift(time) {
  return { x: WIND.x * time, z: WIND.z * time };
}

/** Vertical air velocity (m/s) at a point: thermals plus ridge lift. */
export function liftAt(x, y, z, ground, time, info) {
  const d = drift(time);
  let lift = 0;
  let nearest = Infinity;
  for (const t of thermals) {
    const tx = wrapNear(t.x + d.x, x);
    const tz = wrapNear(t.z + d.z, z);
    const dist = Math.hypot(x - tx, z - tz);
    nearest = Math.min(nearest, dist / t.radius);
    if (dist > t.radius * 3) continue;
    const core = Math.exp(-((dist / t.radius) ** 2));
    const ring = Math.exp(-(((dist - 1.9 * t.radius) / t.radius) ** 2)) * 0.45;
    const overLand = heightAt(tx, tz) > 4 ? 1 : 0.3;
    const height = smoothstep(0, 60, y - ground) * (1 - smoothstep(t.base - 120, t.base + 20, y));
    lift += (t.strength * core - ring) * overLand * height;
  }
  // Wind blowing up a slope rises with it; the lee side sinks.
  const slope = (heightAt(x + 12, z) - heightAt(x - 12, z)) / 24 * WIND.x
    + (heightAt(x, z + 12) - heightAt(x, z - 12)) / 24 * WIND.z;
  const ridge = clamp(slope * 1.6, -2.5, 5) * Math.exp(-Math.max(0, y - ground) / 140);
  if (info) {
    info.thermal = nearest;
    info.ridge = ridge;
  }
  return lift + ridge;
}

/** Finds a coastal start facing the nearest mountains. */
export function findSpawn() {
  for (let r = 0; r < 20000; r += 150) {
    for (let a = 0; a < Math.PI * 2; a += 0.35) {
      const x = Math.cos(a) * r;
      const z = Math.sin(a) * r;
      const h = heightAt(x, z);
      if (h < 3 || h > 25) continue;
      let best = -Infinity;
      let heading = 0;
      for (let k = 0; k < 16; k++) {
        const b = (k / 16) * Math.PI * 2;
        // Heading convention matches the flight model: forward = (-sin, -cos).
        const peak = heightAt(x - Math.sin(b) * 1800, z - Math.cos(b) * 1800);
        if (peak > best) { best = peak; heading = b; }
      }
      if (best > 250) return { x, z, heading };
    }
  }
  return { x: 0, z: 0, heading: 0 };
}
