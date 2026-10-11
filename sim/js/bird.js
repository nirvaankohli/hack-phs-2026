// A procedural bald eagle with jointed wings. Forward is -Z, right wing is +X.

import * as THREE from 'three';

function featherTexture(base, edge, rows) {
  const w = 256;
  const h = 256;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, w, h);
  // Overlapping feather rows: each feather is a long rounded stroke with a lighter rim.
  for (let r = 0; r < rows; r++) {
    const y0 = (r / rows) * h;
    for (let x = -10; x < w + 10; x += 9 + Math.random() * 4) {
      const len = h / rows * (1.4 + Math.random() * 0.5);
      ctx.strokeStyle = edge;
      ctx.globalAlpha = 0.25 + Math.random() * 0.2;
      ctx.lineWidth = 7;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x + 3, y0 + len);
      ctx.stroke();
      ctx.strokeStyle = base;
      ctx.globalAlpha = 0.9;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x + 3, y0 + len - 4);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(0,0,0,0.5)';
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + 1, y0 + 2);
      ctx.lineTo(x + 3, y0 + len - 6);
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

/** Flat wing panel from outline points [x outward, y forward], with UVs spanning its bounds. */
function panel(points) {
  const shape = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
  const geometry = new THREE.ShapeGeometry(shape);
  geometry.computeBoundingBox();
  const { min, max } = geometry.boundingBox;
  const p = geometry.attributes.position;
  const uv = geometry.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    // Feathers run front to back, so V follows the chord.
    uv.setXY(i, (p.getX(i) - min.x) / (max.x - min.x), (p.getY(i) - min.y) / (max.y - min.y));
  }
  // Shape Y (forward) becomes -Z.
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}

const ARM = [
  [0, 0.11], [0.2, 0.1], [0.4, 0.07], [0.5, 0.04],
  [0.5, -0.27], [0.44, -0.31], [0.39, -0.27], [0.33, -0.32], [0.27, -0.28], [0.21, -0.33],
  [0.15, -0.29], [0.09, -0.33], [0.03, -0.28], [0, -0.22],
];
const HAND = [
  [0, 0.04], [0.18, 0.06], [0.36, 0.04], [0.5, -0.01],
  // Slotted primaries: the "fingers" at an eagle's wingtip.
  [0.66, -0.02], [0.5, -0.07], [0.69, -0.09], [0.5, -0.13], [0.68, -0.16], [0.49, -0.19],
  [0.63, -0.23], [0.45, -0.24], [0.54, -0.29],
  [0.36, -0.29], [0.26, -0.31], [0.17, -0.28], [0.08, -0.31], [0, -0.27],
];

export function createBird() {
  const brown = new THREE.MeshStandardMaterial({ color: 0x3a2618, roughness: 0.85 });
  const white = new THREE.MeshStandardMaterial({ color: 0xf2efe8, roughness: 0.8 });
  const yellow = new THREE.MeshStandardMaterial({ color: 0xe8b622, roughness: 0.5 });
  const wingMaterial = new THREE.MeshStandardMaterial({
    map: featherTexture('#3d2819', '#8a6a48', 5), roughness: 0.85, side: THREE.DoubleSide,
  });
  const tailMaterial = new THREE.MeshStandardMaterial({
    map: featherTexture('#efebe2', '#b9b2a6', 1), roughness: 0.8, side: THREE.DoubleSide,
  });

  const root = new THREE.Group();     // positioned and rotated by the flight model
  const model = new THREE.Group();    // body pose (pitch offset, landing stance)
  root.add(model);

  const body = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), brown);
  body.scale.set(0.14, 0.13, 0.42);
  model.add(body);
  const chest = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), brown);
  chest.scale.set(0.13, 0.13, 0.2);
  chest.position.set(0, -0.02, -0.18);
  model.add(chest);

  const head = new THREE.Group();
  head.position.set(0, 0.06, -0.4);
  model.add(head);
  const skull = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), white);
  skull.scale.set(0.085, 0.085, 0.11);
  head.add(skull);
  const neck = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), white);
  neck.scale.set(0.095, 0.09, 0.1);
  neck.position.set(0, -0.02, 0.07);
  head.add(neck);
  const beak = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.12, 10).rotateX(-Math.PI / 2), yellow);
  beak.position.set(0, -0.01, -0.13);
  head.add(beak);
  const hook = new THREE.Mesh(new THREE.SphereGeometry(0.022, 8, 6), yellow);
  hook.position.set(0, -0.025, -0.17);
  head.add(hook);
  const eyeMaterial = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.2 });
  for (const side of [-1, 1]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.014, 8, 6), eyeMaterial);
    eye.position.set(side * 0.06, 0.02, -0.06);
    head.add(eye);
  }

  const tail = new THREE.Group();
  tail.position.set(0, 0.01, 0.34);
  model.add(tail);
  const tailFan = new THREE.Mesh(panel([
    [-0.05, 0], [0.05, 0], [0.13, -0.3], [0.08, -0.34], [0, -0.32], [-0.08, -0.34], [-0.13, -0.3],
  ]), tailMaterial);
  tail.add(tailFan);

  const legs = new THREE.Group();
  legs.position.set(0, -0.1, 0.05);
  legs.visible = false;
  model.add(legs);
  for (const side of [-1, 1]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.022, 0.22, 6), yellow);
    leg.position.set(side * 0.06, -0.1, 0);
    legs.add(leg);
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.02, 0.1), yellow);
    foot.position.set(side * 0.06, -0.21, -0.02);
    legs.add(foot);
  }

  const armGeometry = panel(ARM);
  const handGeometry = panel(HAND);
  const wings = [-1, 1].map((side) => {
    const shoulder = new THREE.Group();
    shoulder.rotation.order = 'YXZ';
    shoulder.position.set(side * 0.09, 0.05, -0.12);
    shoulder.scale.x = side;   // mirror the left wing
    model.add(shoulder);
    const arm = new THREE.Mesh(armGeometry, wingMaterial);
    shoulder.add(arm);
    const wrist = new THREE.Group();
    wrist.position.set(0.48, 0, -0.04);
    shoulder.add(wrist);
    const hand = new THREE.Mesh(handGeometry, wingMaterial);
    hand.position.set(-0.02, 0, 0.02);
    wrist.add(hand);
    return { shoulder, wrist, side };
  });

  root.traverse((o) => { if (o.isMesh) o.castShadow = true; });

  const state = { phase: 0, flap: 0, time: 0, hand: 0 };

  /**
   * pose: { stroke -1..1 (where the wings are in their beat; + = raised), or
   *         flapping 0..1 for an automatic beat (the circling hawks),
   *         tuck 0..1 (dive), bank radians, landed bool, stall 0..1, speed }
   */
  function animate(dt, pose) {
    state.time += dt;
    state.flap += ((pose.flapping > 0 ? 1 : 0) - state.flap) * (1 - Math.exp(-dt * 10));
    state.phase += dt * (pose.landed ? 0 : 9.5 + (pose.stall || 0) * 6);
    // The player's wing sets the stroke directly; the hand trails the arm a little.
    const beat = pose.stroke ?? Math.sin(state.phase) * state.flap;
    state.hand += (beat - state.hand) * (1 - Math.exp(-dt * 14));
    const lag = pose.stroke === undefined ? Math.sin(state.phase - 0.9) * state.flap : state.hand;
    const tuck = pose.landed ? 1 : pose.tuck;
    const flutter = (pose.stall || 0) * Math.sin(state.time * 31) * 0.08;
    for (const w of wings) {
      // Slight dihedral when gliding; the wing on the inside of a turn drops a little.
      const glide = 0.08 + Math.sin(state.time * 1.3) * 0.015;
      const roll = -pose.bank * 0.12 * w.side;
      const raise = pose.landed ? 0.12 : glide + roll + beat * 0.95 + flutter;
      // The shoulder rotates after its own mirroring, so sweep and raise flip for
      // the left side; twist about the span axis and the wrist (inside the mirrored
      // space) don't. Perched, the wings swing back and stand on edge along the body.
      const sweep = pose.landed ? 1.45 : tuck * 0.85;
      w.shoulder.rotation.set(pose.landed ? 1.2 : 0, -sweep * w.side, raise * w.side);
      w.wrist.rotation.set(0, pose.landed ? -0.2 : -tuck * 1.1, pose.landed ? 0 : lag * 0.6 - beat * 0.15);
      w.wrist.scale.x = pose.landed ? 0.6 : 1;
      w.shoulder.position.y = 0.05 + beat * 0.02;
    }
    tail.rotation.x = -0.05 - (pose.pitchInput || 0) * 0.25;
    tail.scale.x = 1 + (1 - Math.min(1, (pose.speed || 15) / 18)) * 0.6 - tuck * 0.3;
    // Birds hold their heads level while the body banks.
    head.rotation.z = pose.landed ? 0 : pose.bank * 0.55;
    head.rotation.y = pose.landed ? Math.sin(state.time * 0.7) * 0.6 : 0;
    legs.visible = pose.landed;
    model.position.y = pose.landed ? 0.32 : -beat * 0.03;
    model.rotation.x = pose.landed ? 0.35 : 0;
  }

  return { root, animate, head, body: [body, chest, head, tail] };
}
