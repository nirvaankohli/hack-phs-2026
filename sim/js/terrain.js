// Streams terrain chunks (with trees) around the bird at three levels of detail.

import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry32 } from './noise.js';
import { forestAt, groundColor, heightAt } from './world.js';

export const CHUNK = 400;
const LODS = [
  { segments: 96, trees: true, shadows: true },
  { segments: 40, trees: true, shadows: false },
  { segments: 14, trees: false, shadows: false },
];
const SKIRT = 30;            // hides cracks where chunks of different detail meet
const TREE_CANDIDATES = 900;

function detailTexture() {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const image = ctx.createImageData(size, size);
  const random = mulberry32(99);
  for (let i = 0; i < size * size; i++) {
    const v = 205 + random() * 50;
    image.data[i * 4] = image.data[i * 4 + 1] = image.data[i * 4 + 2] = v;
    image.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  // A few soft blotches so the grain isn't uniform static; drawn wrapped so it tiles.
  for (let i = 0; i < 160; i++) {
    const shade = random() < 0.5 ? 0 : 255;
    ctx.fillStyle = `rgba(${shade},${shade},${shade},0.05)`;
    ctx.beginPath();
    const x = random() * size;
    const y = random() * size;
    const r = 4 + random() * 18;
    for (const dx of [-size, 0, size]) {
      for (const dy of [-size, 0, size]) {
        ctx.moveTo(x + dx + r, y + dy);
        ctx.arc(x + dx, y + dy, r, 0, Math.PI * 2);
      }
    }
    ctx.fill();
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

function colored(geometry, rgb) {
  geometry.deleteAttribute('uv');
  const color = new THREE.Color().setRGB(...rgb, THREE.SRGBColorSpace);
  const count = geometry.attributes.position.count;
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) color.toArray(colors, i * 3);
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geometry;
}

function treeGeometries() {
  const trunk = (r, h) => colored(new THREE.CylinderGeometry(r * 0.7, r, h, 6).translate(0, h / 2 - 0.5, 0),
    [0.29, 0.21, 0.15]);
  const needles = [0.09, 0.2, 0.11];
  const pine = mergeGeometries([
    trunk(0.35, 4.5),
    colored(new THREE.ConeGeometry(3.3, 6.5, 9).translate(0, 6, 0), needles),
    colored(new THREE.ConeGeometry(2.6, 5.5, 9).translate(0, 8.8, 0), needles),
    colored(new THREE.ConeGeometry(1.7, 4.5, 9).translate(0, 11.8, 0), needles),
  ]);
  let crown = mergeVertices(new THREE.IcosahedronGeometry(4.2, 2).deleteAttribute('normal').deleteAttribute('uv'));
  const random = mulberry32(5);
  const p = crown.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const k = 0.82 + random() * 0.32;
    p.setXYZ(i, p.getX(i) * k, p.getY(i) * k * 0.82, p.getZ(i) * k);
  }
  crown.translate(0, 8.5, 0);
  crown.computeVertexNormals();
  const broadleaf = mergeGeometries([trunk(0.45, 6), colored(crown, [0.19, 0.31, 0.11])]);
  return [pine, broadleaf];
}

export class Terrain {
  constructor(scene, { radius = 8, treeLod = 1, shadows = true, detail = 1 } = {}) {
    this.scene = scene;
    this.radius = radius;
    this.detail = detail;
    this.treeLod = treeLod;
    this.shadows = shadows;
    this.chunks = new Map();
    this.material = new THREE.MeshStandardMaterial({
      vertexColors: true, map: detailTexture(), roughness: 0.97, metalness: 0,
    });
    this.treeMaterial = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9 });
    this.treeGeometries = treeGeometries();
  }

  /** Applies new view distance and tree/shadow settings; chunks rebuild on the next update. */
  setQuality({ radius, treeLod, shadows, detail = 1 }) {
    Object.assign(this, { radius, treeLod, shadows, detail });
    for (const chunk of this.chunks.values()) this.dispose(chunk);
    this.chunks.clear();
  }

  /** Builds or rebuilds chunks near (x, z), spending at most `budgetMs` (Infinity = all). */
  update(x, z, budgetMs = 6) {
    const cx = Math.floor(x / CHUNK);
    const cz = Math.floor(z / CHUNK);
    const wanted = [];
    for (let dz = -this.radius; dz <= this.radius; dz++) {
      for (let dx = -this.radius; dx <= this.radius; dx++) {
        const d = Math.max(Math.abs(dx), Math.abs(dz));
        const lod = d <= 1 ? 0 : d <= 2 ? 1 : 2;
        const key = `${cx + dx},${cz + dz}`;
        const chunk = this.chunks.get(key);
        if (!chunk || chunk.lod !== lod) wanted.push({ key, x: cx + dx, z: cz + dz, lod, d });
      }
    }
    for (const [key, chunk] of this.chunks) {
      const [kx, kz] = key.split(',').map(Number);
      if (Math.max(Math.abs(kx - cx), Math.abs(kz - cz)) > this.radius + 1) {
        this.dispose(chunk);
        this.chunks.delete(key);
      }
    }
    wanted.sort((a, b) => a.d - b.d);
    const start = performance.now();
    for (const job of wanted) {
      if (performance.now() - start > budgetMs) break;
      const old = this.chunks.get(job.key);
      if (old) this.dispose(old);
      this.chunks.set(job.key, this.build(job.x, job.z, job.lod));
    }
    return wanted.length;
  }

  dispose(chunk) {
    for (const object of chunk.objects) {
      this.scene.remove(object);
      if (object.isInstancedMesh) object.dispose();
      else object.geometry.dispose();
    }
  }

  build(cx, cz, lod) {
    const { trees, shadows } = LODS[lod];
    const n = Math.max(6, Math.round(LODS[lod].segments * this.detail));
    const step = CHUNK / n;
    const x0 = cx * CHUNK;
    const z0 = cz * CHUNK;
    // Heights include a one-sample border so normals match across chunk edges.
    const W = n + 3;
    const heights = new Float32Array(W * W);
    for (let j = 0; j < W; j++) {
      for (let i = 0; i < W; i++) heights[j * W + i] = heightAt(x0 + (i - 1) * step, z0 + (j - 1) * step);
    }
    const H = (i, j) => heights[(j + 1) * W + (i + 1)];
    const surface = (n + 1) * (n + 1);
    const total = surface + 4 * (n + 1);
    const positions = new Float32Array(total * 3);
    const normals = new Float32Array(total * 3);
    const colors = new Float32Array(total * 3);
    const uvs = new Float32Array(total * 2);
    const rgb = [0, 0, 0];
    const color = new THREE.Color();
    const vertex = (v, i, j, drop) => {
      const h = H(i, j);
      let nx = H(i - 1, j) - H(i + 1, j);
      let nz = H(i, j - 1) - H(i, j + 1);
      let ny = 2 * step;
      const len = Math.hypot(nx, ny, nz);
      nx /= len; ny /= len; nz /= len;
      positions.set([i * step, h - drop, j * step], v * 3);
      normals.set([nx, ny, nz], v * 3);
      groundColor(x0 + i * step, z0 + j * step, h, ny, rgb);
      color.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace).toArray(colors, v * 3);
      // 400 m chunks hold a whole number of 8 m texture tiles, so the grain is seamless.
      uvs.set([i * step / 8, j * step / 8], v * 2);
    };
    for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) vertex(j * (n + 1) + i, i, j, 0);
    const indices = [];
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < n; i++) {
        const a = j * (n + 1) + i;
        const b = a + 1;
        const c = a + n + 1;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }
    const edges = [
      (k) => [k, 0], (k) => [n, k], (k) => [n - k, n], (k) => [0, n - k],
    ];
    let v = surface;
    for (const edge of edges) {
      const first = v;
      for (let k = 0; k <= n; k++) {
        const [i, j] = edge(k);
        vertex(v++, i, j, SKIRT);
      }
      for (let k = 0; k < n; k++) {
        const [i0, j0] = edge(k);
        const [i1, j1] = edge(k + 1);
        const top0 = j0 * (n + 1) + i0;
        const top1 = j1 * (n + 1) + i1;
        const low0 = first + k;
        const low1 = first + k + 1;
        // Both windings, so the skirt shows from either side.
        indices.push(top0, low0, top1, top1, low0, low1, top0, top1, low0, top1, low1, low0);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    geometry.setIndex(indices);
    geometry.computeBoundingSphere();
    const mesh = new THREE.Mesh(geometry, this.material);
    mesh.position.set(x0, 0, z0);
    mesh.receiveShadow = this.shadows;
    mesh.matrixAutoUpdate = false;
    mesh.updateMatrix();
    this.scene.add(mesh);
    const objects = [mesh];
    if (trees && lod <= this.treeLod) objects.push(...this.plantTrees(cx, cz, shadows && this.shadows));
    return { lod, objects };
  }

  plantTrees(cx, cz, castShadow) {
    const random = mulberry32((cx * 73856093) ^ (cz * 19349663));
    const placed = [[], []];
    for (let k = 0; k < TREE_CANDIDATES; k++) {
      // Always draw the same five numbers so every detail level grows the same forest.
      const [rx, rz, keep, kind, size] = [random(), random(), random(), random(), random()];
      const x = (cx + rx) * CHUNK;
      const z = (cz + rz) * CHUNK;
      const h = heightAt(x, z);
      if (keep > forestAt(x, z, h) * 0.85 + 0.01 || h < 4) continue;
      const slope = Math.abs(heightAt(x + 3, z) - h) + Math.abs(heightAt(x, z + 3) - h);
      if (slope > 3.2) continue;
      const pine = kind < 0.25 + h / 300;
      placed[pine ? 0 : 1].push({ x, y: h - 0.6, z, scale: 0.65 + size * 0.75, spin: keep * 40, tint: size });
    }
    const dummy = new THREE.Object3D();
    const tint = new THREE.Color();
    const meshes = [];
    placed.forEach((list, type) => {
      if (!list.length) return;
      const mesh = new THREE.InstancedMesh(this.treeGeometries[type], this.treeMaterial, list.length);
      list.forEach((t, i) => {
        dummy.position.set(t.x, t.y, t.z);
        dummy.rotation.set(0, t.spin, 0);
        dummy.scale.setScalar(t.scale);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
        const k = 0.8 + t.tint * 0.4;
        mesh.setColorAt(i, tint.setRGB(k, k * (0.95 + t.tint * 0.1), k * 0.9));
      });
      mesh.castShadow = castShadow;
      mesh.receiveShadow = this.shadows;
      mesh.computeBoundingSphere();
      this.scene.add(mesh);
      meshes.push(mesh);
    });
    return meshes;
  }
}
