import * as THREE from 'three';
import { Sound } from './audio.js';
import { createBird } from './bird.js';
import { Clouds } from './clouds.js';
import { Environment, PRESETS } from './environment.js';
import { Flight } from './flight.js';
import { Input } from './input.js';
import { clamp, smoothstep } from './noise.js';
import { Terrain } from './terrain.js';
import { drift, findSpawn, heightAt, thermals, wrapNear } from './world.js';

const QUALITY = {
  // For 8 GB laptops on integrated graphics: renders at reduced resolution and
  // upscales, no trees or shadows, coarse terrain, short view, half the cloud puffs.
  ultra: { name: 'Ultra low', pixelRatio: 0.6, shadows: false, radius: 4, treeLod: -1, detail: 0.5,
    fog: 0.001, clouds: 0.5, antialias: false },
  low: { name: 'Low', pixelRatio: 1, shadows: false, radius: 6, treeLod: 0, detail: 0.75, fog: 0.00068 },
  medium: { name: 'Medium', pixelRatio: 1.25, shadows: true, radius: 8, treeLod: 1, fog: 0.00052 },
  high: { name: 'High', pixelRatio: 2, shadows: true, radius: 9, treeLod: 1, fog: 0.00046 },
};
const LEVELS = Object.keys(QUALITY);
// ?quality=low in the URL wins; otherwise the last choice made with Q is remembered.
let quality = new URLSearchParams(location.search).get('quality');
try { quality ||= localStorage.getItem('skyborne-quality'); } catch { /* storage blocked */ }
if (!QUALITY[quality]) quality = 'medium';
const SETTINGS = QUALITY[quality];

// Antialiasing can only be chosen when the renderer is created, so it follows
// the level the page opened with.
const renderer = new THREE.WebGLRenderer({ antialias: SETTINGS.antialias !== false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, SETTINGS.pixelRatio));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;  // the sun's castShadow switches shadows per quality level
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.3, 30000);
const environment = new Environment(renderer, scene, SETTINGS);
const clouds = new Clouds(scene);
let presetIndex = 0;
function applyPreset(index) {
  presetIndex = index;
  environment.apply(PRESETS[index]);
  clouds.setLight(PRESETS[index], scene.fog);
}
applyPreset(0);

environment.setQuality(SETTINGS);
clouds.setDensity(SETTINGS.clouds ?? 1);
const terrain = new Terrain(scene, SETTINGS);

function setQuality(level) {
  quality = level;
  const settings = QUALITY[level];
  try { localStorage.setItem('skyborne-quality', level); } catch { /* storage blocked */ }
  renderer.setPixelRatio(Math.min(devicePixelRatio, settings.pixelRatio));
  renderer.setSize(innerWidth, innerHeight);
  environment.setQuality(settings);
  clouds.setLight(PRESETS[presetIndex], scene.fog);
  clouds.setDensity(settings.clouds ?? 1, camera.position, time);
  terrain.setQuality(settings);
  terrain.update(flight.position.x, flight.position.z, Infinity);
}
const flight = new Flight();
const input = new Input();
const sound = new Sound();
const bird = createBird();
scene.add(bird.root);

// Hawks circling in nearby thermals show where the rising air is, as in real life.
const hawks = Array.from({ length: 5 }, (_, i) => {
  const hawk = createBird();
  scene.add(hawk.root);
  return { ...hawk, index: i, thermal: null, angle: i * 1.7, height: 0 };
});

// Air streaks that sell speed in a fast dive.
const STREAKS = 140;
const streakPoints = Array.from({ length: STREAKS }, () => new THREE.Vector3(0, -1e5, 0));
const streakGeometry = new THREE.BufferGeometry();
streakGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(STREAKS * 6), 3));
const streaks = new THREE.LineSegments(streakGeometry, new THREE.LineBasicMaterial({
  color: 0xffffff, transparent: true, opacity: 0, depthWrite: false, fog: false,
}));
streaks.frustumCulled = false;
scene.add(streaks);

// Spray or dust when a landing goes wrong.
const SPRAY = 90;
const sprayGeometry = new THREE.BufferGeometry();
sprayGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(SPRAY * 3), 3));
const spray = new THREE.Points(sprayGeometry, new THREE.PointsMaterial({
  color: 0xffffff, size: 0.35, transparent: true, opacity: 0.9, depthWrite: false,
}));
spray.frustumCulled = false;
spray.visible = false;
const sprayVelocity = Array.from({ length: SPRAY }, () => new THREE.Vector3());
scene.add(spray);

function burst(position, water) {
  const p = sprayGeometry.attributes.position;
  spray.material.color.set(water ? 0xf4f8fa : 0x7a6a55);
  for (let i = 0; i < SPRAY; i++) {
    p.setXYZ(i, position.x, position.y + 0.2, position.z);
    const a = Math.random() * Math.PI * 2;
    const r = Math.random() * (water ? 4 : 2.5);
    sprayVelocity[i].set(Math.cos(a) * r, 3 + Math.random() * (water ? 9 : 4), Math.sin(a) * r);
  }
  p.needsUpdate = true;
  spray.visible = true;
}

// ---- HUD -----------------------------------------------------------------

const $ = (id) => document.getElementById(id);
const hud = {
  alt: $('alt'), agl: $('agl'), angle: $('angle'), speed: $('speed'), vario: $('vario'), stamina: $('stamina').firstElementChild,
  strip: $('compass-strip'), message: $('message'), wing: $('wingicon'), source: $('source'),
  flap: $('flapdot'), whiteout: $('whiteout'), fade: $('fade'), overlay: $('overlay'), start: $('start'),
};
const NAMES = { 0: 'N', 45: 'NE', 90: 'E', 135: 'SE', 180: 'S', 225: 'SW', 270: 'W', 315: 'NW' };
for (let d = -360; d <= 720; d += 15) {
  const mark = document.createElement('span');
  const n = ((d % 360) + 360) % 360;
  mark.textContent = NAMES[n] ?? '·';
  mark.style.cssText = `position:absolute;left:${(d + 360) * 2}px;transform:translateX(-50%);`
    + (NAMES[n] ? (n % 90 ? 'opacity:.7' : 'color:var(--accent);font-weight:600') : 'opacity:.45');
  hud.strip.append(mark);
}

let message = { until: 0, priority: 0 };
function say(text, sub = '', seconds = 2.5, priority = 1) {
  const now = performance.now() / 1000;
  if (now < message.until && priority < message.priority) return;
  message = { until: now + seconds, priority };
  hud.message.innerHTML = text + (sub ? `<small>${sub}</small>` : '');
  hud.message.style.opacity = 1;
}

// ---- State and keys -------------------------------------------------------

let started = false;
let paused = true;
let cameraMode = 0;
const CAMERA_MODES = ['Chase camera', 'Wide camera', "Eagle's eye"];
let time = 0;
let hintCooldown = 0;

function setPaused(value) {
  paused = value;
  hud.overlay.style.display = paused ? 'grid' : 'none';
  hud.start.innerHTML = `<span class="pulse">${started ? 'Paused — press Space, Enter or click to continue'
    : 'Press Space, Enter or click to fly'}</span>`;
}

function begin() {
  sound.start();
  if (sound.ctx?.state === 'suspended') sound.ctx.resume();
  started = true;
  setPaused(false);
}

hud.overlay.addEventListener('click', () => { if (ready) begin(); });
addEventListener('keydown', (e) => {
  if (!ready) return;
  if (paused) {
    if (['Space', 'Enter'].includes(e.code)) begin();
    return;
  }
  switch (e.code) {
    case 'Escape': case 'KeyP': case 'KeyH': setPaused(true); break;
    case 'KeyC':
      cameraMode = (cameraMode + 1) % CAMERA_MODES.length;
      say(CAMERA_MODES[cameraMode], '', 1.5, 2);
      break;
    case 'KeyT':
      applyPreset((presetIndex + 1) % PRESETS.length);
      say(PRESETS[presetIndex].name, '', 1.5, 2);
      break;
    case 'KeyQ':
      setQuality(LEVELS[(LEVELS.indexOf(quality) + 1) % LEVELS.length]);
      say(`Graphics: ${QUALITY[quality].name}`, '', 1.5, 2);
      break;
    case 'KeyV':
      sound.vario = !sound.vario;
      say(`Variometer ${sound.vario ? 'on' : 'off'}`, '', 1.5, 2);
      break;
    case 'KeyM':
      sound.setMuted(!sound.muted);
      say(sound.muted ? 'Muted' : 'Sound on', '', 1.5, 2);
      break;
    case 'KeyI':
      input.invertPitch = !input.invertPitch;
      say(input.invertPitch ? 'Pitch inverted: down arrow climbs' : 'Pitch: up arrow climbs', '', 2, 2);
      break;
    case 'KeyR':
      flight.respawn();
      input.level();
      break;
  }
});

addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});

// ---- Per-frame updates -------------------------------------------------------

const forward = new THREE.Vector3();
const cameraOffset = new THREE.Vector3(0, 2, 6);
const desired = new THREE.Vector3();
const look = new THREE.Vector3();
let cameraRoll = 0;

function updateBird(dt) {
  const f = flight;
  bird.root.position.copy(f.position);
  if (f.state === 'landed') {
    bird.root.rotation.set(0, f.heading, 0, 'YXZ');
  } else if (f.state === 'flying') {
    // Nose rides a little high when slow, as the wing needs more angle of attack.
    const attack = 0.12 * (1 - smoothstep(8, 22, f.speed)) + f.stall * 0.35;
    bird.root.rotation.set(f.gamma + attack, f.heading, -f.bank, 'YXZ');
  }
  bird.root.visible = !(f.state === 'crashed' && f.stateTime > 0.15);
  bird.animate(dt, {
    // Wings mirror the player's stroke; a stalled bird flails on its own.
    stroke: f.stall > 0.6 && f.state === 'flying' ? Math.sin(time * 14) * 0.8 : input.stroke,
    tuck: f.tuck, bank: f.bank, landed: f.state === 'landed', stall: f.stall,
    speed: f.speed, pitchInput: input.pitch,
  });
  const eye = cameraMode === 2;
  for (const part of bird.body) part.visible = !eye;
}

function updateCamera(dt) {
  const f = flight;
  f.forward(forward);
  const k = 1 - Math.exp(-dt * 4.5);
  if (cameraMode === 2 && f.state !== 'crashed') {
    bird.root.updateMatrixWorld(true);
    bird.head.getWorldPosition(desired);
    camera.position.copy(desired).addScaledVector(forward, 0.05);
    look.copy(camera.position).addScaledVector(forward, 10);
    camera.lookAt(look);
    cameraRoll += (-f.bank - cameraRoll) * k;
    camera.rotateZ(cameraRoll * 0.8);
    camera.near = 0.08;
  } else if (f.state !== 'crashed') {
    const [distance, height] = cameraMode === 0 ? [5.5, 1.4] : [13, 3.5];
    const g = f.state === 'landed' ? 0 : f.gamma * 0.55;
    desired.set(Math.sin(f.heading) * Math.cos(g) * distance, height - Math.sin(g) * distance,
      Math.cos(f.heading) * Math.cos(g) * distance);
    cameraOffset.lerp(desired, k);
    camera.position.copy(f.position).add(cameraOffset);
    // Never let the camera dip under the ground or sea.
    const floor = Math.max(heightAt(camera.position.x, camera.position.z), 0) + 0.8;
    camera.position.y = Math.max(camera.position.y, floor);
    look.copy(f.position).addScaledVector(forward, 6).y += 0.5;
    camera.lookAt(look);
    cameraRoll += (-f.bank - cameraRoll) * k;
    camera.rotateZ(cameraRoll * 0.4);
    camera.near = 0.3;
  } else {
    camera.lookAt(f.position);
  }
  // Speed: wider view and a little buffeting in a fast stoop.
  const fast = smoothstep(18, 60, f.speed);
  camera.fov += (60 + fast * 22 - camera.fov) * k;
  const shake = smoothstep(35, 65, f.speed) * 0.004;
  camera.rotation.x += (Math.random() - 0.5) * shake;
  camera.rotation.y += (Math.random() - 0.5) * shake;
  camera.updateProjectionMatrix();
}

function updateHawks(dt) {
  const d = drift(time);
  for (const hawk of hawks) {
    const t = hawk.thermal;
    const tx = t ? wrapNear(t.x + d.x, flight.position.x) : 0;
    const tz = t ? wrapNear(t.z + d.z, flight.position.z) : 0;
    if (!t || Math.hypot(tx - flight.position.x, tz - flight.position.z) > 3500) {
      // Move this hawk to a nearby thermal the others aren't using.
      const taken = new Set(hawks.map((h) => h.thermal));
      const options = thermals
        .filter((th) => !taken.has(th) && heightAt(wrapNear(th.x + d.x, flight.position.x),
          wrapNear(th.z + d.z, flight.position.z)) > 4)
        .map((th) => ({ th, dist: Math.hypot(wrapNear(th.x + d.x, flight.position.x) - flight.position.x,
          wrapNear(th.z + d.z, flight.position.z) - flight.position.z) }))
        .sort((a, b) => a.dist - b.dist);
      hawk.thermal = options[0]?.th ?? null;
      hawk.height = Math.random();
      hawk.root.visible = !!hawk.thermal;
      continue;
    }
    const radius = t.radius * 0.55;
    const speed = 13;
    hawk.angle += speed / radius * dt;
    hawk.height = (hawk.height + dt * 0.004) % 1;
    const ground = Math.max(heightAt(tx, tz), 0);
    const y = Math.max(ground + 90, t.base - 330 + hawk.height * 260);
    hawk.root.position.set(tx + Math.cos(hawk.angle) * radius, y, tz + Math.sin(hawk.angle) * radius);
    // Tangent heading for a counter-clockwise circle, banked into the turn.
    const bank = Math.atan(speed * speed / (radius * 9.81));
    hawk.root.rotation.set(0.02, -hawk.angle + Math.PI, -bank, 'YXZ');
    hawk.animate(dt, {
      flapping: Math.sin(time * 0.35 + hawk.index * 2.1) > 0.92 ? 1 : 0,
      tuck: 0, bank, landed: false, stall: 0, speed,
    });
  }
}

function updateStreaks() {
  const v = flight.velocity;
  const fast = flight.state === 'flying' ? smoothstep(24, 50, flight.speed) : 0;
  streaks.material.opacity = fast * 0.35;
  if (!fast) return;
  const p = streakGeometry.attributes.position.array;
  const right = new THREE.Vector3().crossVectors(forward, THREE.Object3D.DEFAULT_UP).normalize();
  for (let i = 0; i < STREAKS; i++) {
    const s = streakPoints[i];
    const rel = s.clone().sub(camera.position);
    if (rel.dot(forward) < 1 || rel.length() > 60) {
      s.copy(camera.position).addScaledVector(forward, 20 + Math.random() * 40)
        .addScaledVector(right, (Math.random() - 0.5) * 30)
        .add(new THREE.Vector3(0, (Math.random() - 0.5) * 20, 0));
    }
    p.set([s.x, s.y, s.z, s.x - v.x * 0.045, s.y - v.y * 0.045, s.z - v.z * 0.045], i * 6);
  }
  streakGeometry.attributes.position.needsUpdate = true;
}

function updateSpray(dt) {
  if (!spray.visible) return;
  const p = sprayGeometry.attributes.position;
  for (let i = 0; i < SPRAY; i++) {
    sprayVelocity[i].y -= 9.81 * dt;
    p.setXYZ(i, p.getX(i) + sprayVelocity[i].x * dt, p.getY(i) + sprayVelocity[i].y * dt,
      p.getZ(i) + sprayVelocity[i].z * dt);
  }
  p.needsUpdate = true;
  spray.material.opacity = Math.max(0, 0.9 - flight.stateTime * 0.45);
  if (flight.state !== 'crashed') spray.visible = false;
}

function updateHud() {
  const f = flight;
  hud.alt.textContent = Math.round(f.position.y);
  hud.agl.textContent = Math.round(Math.max(0, f.altitude ?? 0));
  hud.speed.textContent = Math.round(f.speed * 3.6);
  const vario = f.state === 'flying' ? f.vario : 0;
  hud.vario.textContent = (vario >= 0 ? '+' : '') + vario.toFixed(1);
  hud.angle.textContent = (f.state === 'flying' ? Math.round(f.gamma * 180 / Math.PI) : 0) + '°';
  hud.vario.style.color = vario > 0.3 ? 'var(--good)' : vario < -3 ? 'var(--bad)' : '';
  hud.stamina.style.width = `${f.stamina * 100}%`;
  const bearing = ((-f.heading * 180 / Math.PI) % 360 + 360) % 360;
  hud.strip.style.transform = `translateX(${160 - (bearing + 360) * 2}px)`;
  hud.wing.setAttribute('transform', `translate(0 ${clamp(-input.pitch, -1, 1) * 18}) rotate(${input.roll * 30})`);
  hud.source.textContent = input.source;
  hud.flap.style.opacity = 0.25 + 0.75 * Math.min(1, f.flapPower * 1.5);

  const now = performance.now() / 1000;
  if (f.state === 'landed') say('Perched', 'Flap to take off', 0.2, 3);
  else if (f.state === 'crashed') say(f.crashedInWater ? 'Splash!' : 'Crashed', 'Back to the sky in a moment…', 0.2, 3);
  else if (f.stall > 0.5) say('Stall', 'Lower the wing to dive and regain speed', 0.3, 2);
  else if (f.lift > 1.2 && now > hintCooldown) {
    say(f.air.ridge > 1 ? 'Ridge lift' : 'Rising air', 'Circle here to climb', 2.5);
    hintCooldown = now + 25;
  }
  if (now > message.until) hud.message.style.opacity = 0;
  const whiteout = clouds.insideAt(f.position, time);
  hud.whiteout.style.opacity = whiteout * 0.88;
  hud.fade.style.opacity = f.state === 'crashed' && f.stateTime > 1.6 ? 1 : 0;
}

// ---- Loop ---------------------------------------------------------------

let ready = false;
const clock = new THREE.Clock();
// Suggest a lower setting if the first few seconds of flying run under ~24 fps.
const slow = { frames: 0, seconds: 0, done: false };
function frame() {
  requestAnimationFrame(frame);
  const raw = clock.getDelta();
  const dt = Math.min(raw, 0.05);
  if (!paused && !slow.done && document.visibilityState === 'visible') {
    slow.frames += 1;
    slow.seconds += raw;
    if (slow.seconds > 6) {
      slow.done = true;
      if (slow.frames / slow.seconds < 24 && quality !== LEVELS[0]) {
        say('Running slowly', 'Press Q to lower the graphics', 5, 2);
      }
    }
  }
  if (!paused) {
    time += dt;
    input.update(dt);
    const before = flight.state;
    const event = flight.update(dt, input, time);
    // A held keyboard angle shouldn't send a respawned bird straight back into the ground.
    if (before === 'crashed' && flight.state === 'flying') input.level();
    if (event === 'flap') sound.flap(flight.flapStrength);
    if (event === 'splash' || event === 'crash') {
      burst(flight.position, event === 'splash');
      if (event === 'splash') sound.splash(); else sound.thud();
    }
    sound.update(flight.speed, flight.vario, flight.state === 'flying');
  } else {
    sound.update(0, 0, false);
  }
  updateBird(paused ? 0 : dt);
  updateCamera(dt);
  updateHawks(paused ? 0 : dt);
  updateStreaks();
  updateSpray(paused ? 0 : dt);
  terrain.update(flight.position.x, flight.position.z, 5);
  clouds.update(camera.position, time);
  environment.follow(flight.position, paused ? 0 : dt);
  if (environment.updateHorizon()) clouds.setLight(PRESETS[presetIndex], scene.fog);
  updateHud();
  renderer.render(scene, camera);
}

setPaused(true);
hud.start.textContent = 'Generating world…';
setTimeout(() => {
  const spawn = findSpawn();
  const ground = Math.max(heightAt(spawn.x, spawn.z), 0);
  flight.reset(new THREE.Vector3(spawn.x, ground + 170, spawn.z), spawn.heading);
  terrain.update(spawn.x, spawn.z, Infinity);
  ready = true;
  setPaused(true);
  clock.getDelta();
  frame();
}, 30);

// Handy for debugging from the console.
window.sim = { flight, input, terrain, environment, camera, renderer, scene, applyPreset, get time() { return time; } };
