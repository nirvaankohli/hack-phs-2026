// Live altitude-over-time graph for the HUD: the eagle's altitude as a line,
// the ground beneath it as a filled profile, over a rolling time window.

const WINDOW = 60;        // seconds shown
const SAMPLE_EVERY = 0.1; // seconds between samples
const STEPS = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1000];

const COLORS = {
  line: '#ffcf6e',
  fillTop: 'rgba(255, 207, 110, 0.30)',
  fillBottom: 'rgba(255, 207, 110, 0.02)',
  ground: 'rgba(118, 142, 96, 0.55)',
  groundEdge: 'rgba(170, 196, 140, 0.75)',
  water: 'rgba(90, 150, 200, 0.35)',
  grid: 'rgba(244, 241, 234, 0.12)',
  text: 'rgba(244, 241, 234, 0.62)',
  ring: 'rgba(14, 20, 28, 0.9)',
};

function niceStep(range) {
  return STEPS.find((s) => range / s <= 4) ?? STEPS[STEPS.length - 1];
}

export class AltitudeGraph {
  /** value shows the peak altitude in the window; trend the change over the last 10 s. */
  constructor({ canvas, value, trend }) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.value = value;
    this.trend = trend;
    this.samples = [];       // { t, altitude, ground }
    this.nextSample = 0;
    this.top = 200;          // eased y-axis maximum, so the scale doesn't jump
  }

  push(time, altitude, ground) {
    if (time < this.nextSample) return;
    this.nextSample = time + SAMPLE_EVERY;
    this.samples.push({ t: time, altitude, ground: Math.max(ground, 0) });
    while (this.samples.length && this.samples[0].t < time - WINDOW - 1) this.samples.shift();
  }

  /** Resizes the backing store to the element's CSS size at device resolution. */
  fit() {
    const ratio = Math.min(devicePixelRatio || 1, 2);
    const { width, height } = this.canvas.getBoundingClientRect();
    const w = Math.round(width * ratio);
    const h = Math.round(height * ratio);
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    return { width, height, ratio };
  }

  draw(now) {
    const { width, height, ratio } = this.fit();
    if (!width) return;
    const ctx = this.ctx;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const samples = this.samples;
    if (samples.length < 2) return;

    const latest = samples[samples.length - 1];
    const shown = samples.filter((s) => s.t >= now - WINDOW);
    this.value.textContent = Math.round(Math.max(...shown.map((s) => s.altitude))).toLocaleString();
    const before = samples.find((s) => s.t >= latest.t - 10) ?? samples[0];
    const change = latest.altitude - before.altitude;
    this.trend.textContent = `${change >= 0 ? '▲' : '▼'} ${Math.abs(Math.round(change))} m / 10 s`;
    this.trend.dataset.direction = Math.abs(change) < 2 ? 'level' : change > 0 ? 'up' : 'down';

    // Plot area, leaving room for the y labels on the left and the x labels below.
    const left = 34;
    const right = width - 6;
    const top = 6;
    const bottom = height - 16;
    const highest = Math.max(...samples.map((s) => Math.max(s.altitude, s.ground)));
    const target = Math.max(50, highest * 1.12);
    this.top += (target - this.top) * (target > this.top ? 0.35 : 0.05);
    const step = niceStep(this.top);
    const x = (t) => right - ((now - t) / WINDOW) * (right - left);
    const y = (v) => bottom - (Math.max(0, v) / this.top) * (bottom - top);

    // Recessive gridlines and meter labels.
    ctx.font = '500 10px "Segoe UI", system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'right';
    ctx.lineWidth = 1;
    for (let v = 0; v <= this.top; v += step) {
      const gy = Math.round(y(v)) + 0.5;
      ctx.strokeStyle = COLORS.grid;
      ctx.beginPath();
      ctx.moveTo(left, gy);
      ctx.lineTo(right, gy);
      ctx.stroke();
      ctx.fillStyle = COLORS.text;
      ctx.fillText(v >= 1000 ? `${v / 1000}k` : `${v}`, left - 6, gy);
    }

    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top - 4, right - left, bottom - top + 4);
    ctx.clip();

    // Ground profile under the bird (sea shows as a thin blue band at zero).
    ctx.fillStyle = COLORS.water;
    ctx.fillRect(left, bottom - 2, right - left, 2);
    ctx.beginPath();
    ctx.moveTo(x(samples[0].t), bottom);
    for (const s of samples) ctx.lineTo(x(s.t), y(s.ground));
    ctx.lineTo(x(latest.t), bottom);
    ctx.closePath();
    ctx.fillStyle = COLORS.ground;
    ctx.fill();
    ctx.beginPath();
    samples.forEach((s, i) => (i ? ctx.lineTo(x(s.t), y(s.ground)) : ctx.moveTo(x(s.t), y(s.ground))));
    ctx.strokeStyle = COLORS.groundEdge;
    ctx.lineWidth = 1;
    ctx.stroke();

    // Altitude: soft area fill, then a 2 px line on top.
    const path = new Path2D();
    samples.forEach((s, i) => (i ? path.lineTo(x(s.t), y(s.altitude)) : path.moveTo(x(s.t), y(s.altitude))));
    const area = new Path2D(path);
    area.lineTo(x(latest.t), bottom);
    area.lineTo(x(samples[0].t), bottom);
    area.closePath();
    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, COLORS.fillTop);
    gradient.addColorStop(1, COLORS.fillBottom);
    ctx.fillStyle = gradient;
    ctx.fill(area);
    ctx.strokeStyle = COLORS.line;
    ctx.lineWidth = 2;
    ctx.lineJoin = ctx.lineCap = 'round';
    ctx.stroke(path);
    ctx.restore();

    // "Now" marker: a dot with a dark ring so it reads over the fill.
    const px = x(latest.t);
    const py = y(latest.altitude);
    ctx.beginPath();
    ctx.arc(px, py, 4, 0, Math.PI * 2);
    ctx.fillStyle = COLORS.line;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = COLORS.ring;
    ctx.stroke();

    // Time axis.
    ctx.fillStyle = COLORS.text;
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';
    ctx.fillText(`−${WINDOW} s`, left, height - 3);
    ctx.textAlign = 'center';
    ctx.fillText(`−${WINDOW / 2} s`, (left + right) / 2, height - 3);
    ctx.textAlign = 'right';
    ctx.fillText('now', right, height - 3);
  }
}
