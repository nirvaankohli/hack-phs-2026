// Cumulus clouds built from soft billboards, drawn in one instanced call.
// Each thermal gets a cloud cap, as in the real sky; extra clouds fill the gaps.

import * as THREE from 'three';
import { mulberry32 } from './noise.js';
import { TILE, drift, thermals, wrapNear } from './world.js';

function puffTexture() {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const random = mulberry32(17);
  for (let i = 0; i < 26; i++) {
    const a = random() * Math.PI * 2;
    const d = random() * size * 0.22;
    const x = size / 2 + Math.cos(a) * d;
    const y = size / 2 + Math.sin(a) * d;
    const r = size * (0.14 + random() * 0.16);
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, 'rgba(255,255,255,0.5)');
    g.addColorStop(0.5, 'rgba(255,255,255,0.3)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }
  const texture = new THREE.CanvasTexture(canvas);
  return texture;
}

const vertexShader = /* glsl */ `
  attribute vec3 offset;
  attribute vec4 params;          // size, rotation, shade, opacity
  uniform vec2 uCenter;
  uniform vec2 uDrift;
  uniform float uTile;
  varying vec2 vUv;
  varying float vShade;
  varying float vOpacity;
  varying float vDistance;
  void main() {
    vUv = uv;
    vec2 xz = offset.xz + uDrift;
    xz = uCenter + mod(xz - uCenter + uTile * 0.5, uTile) - uTile * 0.5;
    vec4 view = viewMatrix * vec4(xz.x, offset.y, xz.y, 1.0);
    float c = cos(params.y);
    float s = sin(params.y);
    view.xy += mat2(c, s, -s, c) * position.xy * params.x;
    vDistance = -view.z;
    vShade = params.z;
    vOpacity = params.w;
    gl_Position = projectionMatrix * view;
  }
`;

const fragmentShader = /* glsl */ `
  uniform sampler2D map;
  uniform vec3 uLit;
  uniform vec3 uShade;
  uniform vec3 fogColor;
  uniform float fogDensity;
  varying vec2 vUv;
  varying float vShade;
  varying float vOpacity;
  varying float vDistance;
  void main() {
    float alpha = texture2D(map, vUv).a * vOpacity;
    // Fade puffs that are right on top of the camera instead of clipping them.
    alpha *= smoothstep(4.0, 40.0, vDistance);
    vec3 color = mix(uShade, uLit, vShade);
    float fog = 1.0 - exp(-fogDensity * fogDensity * vDistance * vDistance * 0.6);
    gl_FragColor = vec4(mix(color, fogColor, fog), alpha);
  }
`;

export class Clouds {
  constructor(scene) {
    const random = mulberry32(31);
    this.clusters = [];
    for (const t of thermals) {
      this.clusters.push({ x: t.x, z: t.z, y: t.base, size: t.radius * 1.25 + 50 });
    }
    for (let i = 0; i < 70; i++) {
      this.clusters.push({ x: random() * TILE, z: random() * TILE, y: 520 + random() * 260, size: 70 + random() * 140 });
    }
    const puffs = [];
    for (const c of this.clusters) {
      const count = Math.round(10 + c.size / 9);
      for (let i = 0; i < count; i++) {
        const a = random() * Math.PI * 2;
        const r = Math.sqrt(random()) * c.size;
        const across = r / c.size;
        // Dome shape: flat base, piled higher toward the middle.
        const up = random() * c.size * 0.75 * (1 - across * across);
        puffs.push({
          x: c.x + Math.cos(a) * r, y: c.y + up, z: c.z + Math.sin(a) * r * 0.8,
          size: c.size * (0.55 + random() * 0.5),
          rotation: random() * Math.PI * 2,
          shade: Math.min(1, 0.25 + up / (c.size * 0.6) * 0.75 + random() * 0.1),
          opacity: 0.6 + random() * 0.3,
        });
      }
    }
    this.puffs = puffs;
    const geometry = new THREE.InstancedBufferGeometry();
    const base = new THREE.PlaneGeometry(1, 1);
    geometry.index = base.index;
    geometry.setAttribute('position', base.attributes.position);
    geometry.setAttribute('uv', base.attributes.uv);
    this.offsets = new THREE.InstancedBufferAttribute(new Float32Array(puffs.length * 3), 3);
    this.params = new THREE.InstancedBufferAttribute(new Float32Array(puffs.length * 4), 4);
    this.offsets.setUsage(THREE.DynamicDrawUsage);
    this.params.setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute('offset', this.offsets);
    geometry.setAttribute('params', this.params);
    geometry.instanceCount = puffs.length;
    this.uniforms = {
      map: { value: puffTexture() },
      uCenter: { value: new THREE.Vector2() },
      uDrift: { value: new THREE.Vector2() },
      uTile: { value: TILE },
      uLit: { value: new THREE.Color(1, 1, 1) },
      uShade: { value: new THREE.Color(0.6, 0.65, 0.74) },
      fogColor: { value: new THREE.Color() },
      fogDensity: { value: 0 },
    };
    this.mesh = new THREE.Mesh(geometry, new THREE.ShaderMaterial({
      uniforms: this.uniforms, vertexShader, fragmentShader,
      transparent: true, depthWrite: false,
    }));
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 1;
    scene.add(this.mesh);
    this.frame = 0;
    this.setDensity(1);
  }

  /** Draws every puff at 1, every other puff (each a bit larger) at 0.5. */
  setDensity(fraction, camera = new THREE.Vector3(), time = 0) {
    const every = Math.max(1, Math.round(1 / fraction));
    this.sizeScale = every === 1 ? 1 : 1.3;
    this.order = this.puffs.map((_, i) => i).filter((i) => i % every === 0);
    this.mesh.geometry.instanceCount = this.order.length;
    this.sort(camera, time);
  }

  setLight(preset, fog) {
    this.uniforms.uLit.value.setRGB(...preset.cloudLit, THREE.LinearSRGBColorSpace);
    this.uniforms.uShade.value.setRGB(...preset.cloudShade, THREE.LinearSRGBColorSpace);
    this.uniforms.fogColor.value.copy(fog.color);
    this.uniforms.fogDensity.value = fog.density;
  }

  /** Back-to-front order keeps the alpha blending clean. */
  sort(camera, time) {
    const d = drift(time);
    const dist = this.puffs.map((p) => {
      const x = wrapNear(p.x + d.x, camera.x);
      const z = wrapNear(p.z + d.z, camera.z);
      return (x - camera.x) ** 2 + (p.y - camera.y) ** 2 + (z - camera.z) ** 2;
    });
    this.order.sort((a, b) => dist[b] - dist[a]);
    const o = this.offsets.array;
    const q = this.params.array;
    this.order.forEach((index, i) => {
      const p = this.puffs[index];
      o[i * 3] = p.x; o[i * 3 + 1] = p.y; o[i * 3 + 2] = p.z;
      q[i * 4] = p.size * this.sizeScale; q[i * 4 + 1] = p.rotation; q[i * 4 + 2] = p.shade; q[i * 4 + 3] = p.opacity;
    });
    this.offsets.needsUpdate = true;
    this.params.needsUpdate = true;
  }

  update(camera, time) {
    const d = drift(time);
    this.uniforms.uCenter.value.set(camera.x, camera.z);
    this.uniforms.uDrift.value.set(d.x % TILE, d.z % TILE);
    if (++this.frame % 12 === 0) this.sort(camera, time);
  }

  /** 0..1: how deep inside a cloud a point is (for the white-out effect). */
  insideAt(position, time) {
    const d = drift(time);
    let best = 0;
    for (const c of this.clusters) {
      const x = wrapNear(c.x + d.x, position.x);
      const z = wrapNear(c.z + d.z, position.z);
      const dy = (position.y - c.y - c.size * 0.25) / (c.size * 0.45);
      const r = Math.hypot((position.x - x) / c.size, (position.z - z) / (c.size * 0.8), dy);
      best = Math.max(best, 1 - r);
    }
    return Math.min(1, Math.max(0, best * 2.2));
  }
}
