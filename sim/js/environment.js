// Sky, sunlight, haze and ocean, with a few times of day.

import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';

export const PRESETS = [
  {
    name: 'Morning', elevation: 14, azimuth: 120, turbidity: 6, rayleigh: 1.6, exposure: 0.5,
    sun: [1.0, 0.9, 0.78], sunIntensity: 3.2, cloudLit: [1.0, 0.98, 0.94], cloudShade: [0.74, 0.78, 0.86],
  },
  {
    name: 'Midday', elevation: 52, azimuth: 160, turbidity: 4, rayleigh: 1.2, exposure: 0.42,
    sun: [1.0, 0.97, 0.92], sunIntensity: 3.6, cloudLit: [1.0, 1.0, 1.0], cloudShade: [0.78, 0.82, 0.9],
  },
  {
    name: 'Golden hour', elevation: 4, azimuth: 250, turbidity: 9, rayleigh: 2.4, exposure: 0.62,
    sun: [1.0, 0.68, 0.42], sunIntensity: 2.6, cloudLit: [1.0, 0.82, 0.64], cloudShade: [0.55, 0.52, 0.62],
  },
];

function waterNormals() {
  // Sum of sine waves with whole-number frequencies tiles perfectly.
  const size = 256;
  const waves = [];
  let seed = 3;
  const random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 28; i++) {
    const f = 1 + Math.floor(random() * (4 + i));
    const angle = random() * Math.PI * 2;
    waves.push({
      fx: Math.round(Math.cos(angle) * f), fy: Math.round(Math.sin(angle) * f),
      amp: 1 / (1 + f * 0.8), phase: random() * Math.PI * 2,
    });
  }
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let dx = 0;
      let dy = 0;
      for (const w of waves) {
        const c = Math.cos(2 * Math.PI * (w.fx * x + w.fy * y) / size + w.phase) * w.amp;
        dx += c * w.fx;
        dy += c * w.fy;
      }
      const nx = -dx * 0.05;
      const ny = -dy * 0.05;
      const len = Math.hypot(nx, ny, 1);
      const i = (y * size + x) * 4;
      data[i] = (nx / len * 0.5 + 0.5) * 255;
      data[i + 1] = (ny / len * 0.5 + 0.5) * 255;
      data[i + 2] = (1 / len * 0.5 + 0.5) * 255;
      data[i + 3] = 255;
    }
  }
  const texture = new THREE.DataTexture(data, size, size);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.anisotropy = 8;
  texture.needsUpdate = true;
  return texture;
}

const WATER_TILE = 48;

export class Environment {
  constructor(renderer, scene, { shadows = true } = {}) {
    this.renderer = renderer;
    this.scene = scene;
    this.sky = new Sky();
    this.sky.scale.setScalar(20000);
    scene.add(this.sky);
    this.sunDirection = new THREE.Vector3();
    this.sun = new THREE.DirectionalLight(0xffffff, 3);
    this.sun.castShadow = shadows;
    const s = this.sun.shadow;
    s.mapSize.set(2048, 2048);
    s.camera.left = s.camera.bottom = -110;
    s.camera.right = s.camera.top = 110;
    s.camera.near = 10;
    s.camera.far = 1400;
    s.bias = -0.0004;
    s.normalBias = 0.6;
    // Soft fill from the sky dome so faces turned away from the sun aren't black.
    this.fill = new THREE.HemisphereLight(0xbcd4f0, 0x4a4436, 0.7);
    scene.add(this.sun, this.sun.target, this.fill);
    scene.fog = new THREE.FogExp2(0xbfd1e5, 0.00052);
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.envTarget = null;

    const normals = waterNormals();
    normals.repeat.set(30000 / WATER_TILE, 30000 / WATER_TILE);
    this.water = new THREE.Mesh(
      new THREE.PlaneGeometry(30000, 30000).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color().setRGB(0.012, 0.06, 0.08), roughness: 0.07, metalness: 0,
        normalMap: normals, normalScale: new THREE.Vector2(0.55, 0.55),
      }),
    );
    this.water.receiveShadow = shadows;
    this.waterTime = { value: 0 };
    this.water.material.onBeforeCompile = (shader) => {
      shader.uniforms.uWaterTime = this.waterTime;
      shader.fragmentShader = 'uniform float uWaterTime;\n' + shader.fragmentShader.replace(
        'vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;',
        // Two layers drifting in different directions read as moving water.
        `vec3 mapN = normalize(
          texture2D( normalMap, vNormalMapUv + vec2( uWaterTime * 0.011, uWaterTime * 0.006 ) ).xyz * 2.0 - 1.0 +
          texture2D( normalMap, vNormalMapUv * 0.37 + vec2( -uWaterTime * 0.004, uWaterTime * 0.009 ) ).xyz * 2.0 - 1.0 );`,
      );
    };
    scene.add(this.water);
    this.preset = null;
  }

  /** Shadows on or off, and haze thick enough to hide the edge of the view distance. */
  setQuality({ shadows, fog }) {
    this.sun.castShadow = shadows;
    this.water.receiveShadow = shadows;
    if (!shadows && this.sun.shadow.map) {
      this.sun.shadow.map.dispose();
      this.sun.shadow.map = null;
    }
    this.scene.fog.density = fog;
  }

  apply(preset) {
    this.preset = preset;
    const u = this.sky.material.uniforms;
    u.turbidity.value = preset.turbidity;
    u.rayleigh.value = preset.rayleigh;
    u.mieCoefficient.value = 0.005;
    u.mieDirectionalG.value = 0.8;
    this.sunDirection.setFromSphericalCoords(1,
      THREE.MathUtils.degToRad(90 - preset.elevation), THREE.MathUtils.degToRad(preset.azimuth));
    u.sunPosition.value.copy(this.sunDirection);
    this.renderer.toneMappingExposure = preset.exposure;
    this.sun.color.setRGB(...preset.sun, THREE.SRGBColorSpace);
    this.sun.intensity = preset.sunIntensity;

    // Image-based light from the sky itself.
    const skyScene = new THREE.Scene();
    skyScene.add(this.sky);
    if (this.envTarget) this.envTarget.dispose();
    this.envTarget = this.pmrem.fromScene(skyScene);
    this.scene.environment = this.envTarget.texture;
    this.scene.add(this.sky);
    this.horizonPending = true;
  }

  /**
   * Fog is mixed in after tone mapping and color encoding, so it gets the exact
   * on-screen horizon color, unconverted. Reading pixels can come back empty
   * before the first frame, so this runs (and retries) from the render loop.
   * Returns true once the fog color changed.
   */
  updateHorizon() {
    if (!this.horizonPending) return false;
    const skyScene = new THREE.Scene();
    skyScene.add(this.sky);
    const color = this.sampleHorizon(skyScene);
    this.scene.add(this.sky);
    if (color[0] + color[1] + color[2] === 0) return false;
    this.horizonPending = false;
    this.scene.fog.color.setRGB(...color, THREE.LinearSRGBColorSpace);
    return true;
  }

  sampleHorizon(skyScene) {
    const renderer = this.renderer;
    const camera = new THREE.PerspectiveCamera(4, 1, 1, 30000);
    const gl = renderer.getContext();
    const pixel = new Uint8Array(4);
    const sum = [0, 0, 0];
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    renderer.setRenderTarget(null);
    const samples = 8;
    for (let k = 0; k < samples; k++) {
      const a = (k / samples) * Math.PI * 2;
      camera.lookAt(Math.sin(a), 0.025, Math.cos(a));
      renderer.render(skyScene, camera);
      gl.readPixels(size.x >> 1, size.y >> 1, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
      for (let i = 0; i < 3; i++) sum[i] += pixel[i] / 255 / samples;
    }
    return sum;
  }

  /** Keeps the shadow map and the ocean centered on the bird. */
  follow(position, dt) {
    const snap = 1;
    const target = this.sun.target.position;
    target.set(Math.round(position.x / snap) * snap, Math.round(position.y / snap) * snap,
      Math.round(position.z / snap) * snap);
    this.sun.position.copy(target).addScaledVector(this.sunDirection, 600);
    this.water.position.set(Math.round(position.x / WATER_TILE) * WATER_TILE, 0,
      Math.round(position.z / WATER_TILE) * WATER_TILE);
    this.waterTime.value += dt;
  }
}
