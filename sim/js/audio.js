// Synthesized sound: rushing wind, wingbeats, splashes and a glider-style
// variometer that beeps faster and higher as you climb.

export class Sound {
  constructor() {
    this.ctx = null;
    this.muted = false;
    this.vario = true;
    this.nextBeep = 0;
  }

  /** Browsers only allow audio after a user gesture, so call this from one. */
  start() {
    if (this.ctx) return;
    const ctx = (this.ctx = new AudioContext());
    const length = ctx.sampleRate * 2;
    this.noise = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = this.noise.getChannelData(0);
    for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;

    this.master = ctx.createGain();
    this.master.gain.value = this.muted ? 0 : 0.8;
    this.master.connect(ctx.destination);

    const source = ctx.createBufferSource();
    source.buffer = this.noise;
    source.loop = true;
    this.windFilter = ctx.createBiquadFilter();
    this.windFilter.type = 'bandpass';
    this.windFilter.Q.value = 0.6;
    this.windGain = ctx.createGain();
    this.windGain.gain.value = 0;
    source.connect(this.windFilter).connect(this.windGain).connect(this.master);
    const hiss = ctx.createBiquadFilter();
    hiss.type = 'highpass';
    hiss.frequency.value = 3000;
    this.hissGain = ctx.createGain();
    this.hissGain.gain.value = 0;
    source.connect(hiss).connect(this.hissGain).connect(this.master);
    source.start();
  }

  setMuted(muted) {
    this.muted = muted;
    if (this.master) this.master.gain.value = muted ? 0 : 0.8;
  }

  update(speed, vario, flying) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const s = flying ? Math.min(1, Math.max(0, (speed - 4) / 55)) : 0;
    this.windGain.gain.setTargetAtTime(0.05 + s * s * 0.9, t, 0.1);
    this.hissGain.gain.setTargetAtTime(s * s * s * 0.25, t, 0.1);
    this.windFilter.frequency.setTargetAtTime(250 + speed * 22, t, 0.1);
    if (this.vario && flying && vario > 0.4 && t >= this.nextBeep) {
      const climb = Math.min(vario, 6);
      this.beep(560 + climb * 110, 0.07 + 0.02 * (6 - climb) / 6);
      this.nextBeep = t + 0.55 - climb * 0.065;
    }
  }

  beep(frequency, duration) {
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.value = frequency;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.12, t + 0.01);
    gain.gain.setValueAtTime(0.12, t + duration);
    gain.gain.linearRampToValueAtTime(0, t + duration + 0.02);
    osc.connect(gain).connect(this.master);
    osc.start(t);
    osc.stop(t + duration + 0.05);
  }

  burst(duration, from, to, volume) {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const source = ctx.createBufferSource();
    source.buffer = this.noise;
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(from, t);
    filter.frequency.exponentialRampToValueAtTime(to, t + duration);
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(volume, t + duration * 0.25);
    gain.gain.exponentialRampToValueAtTime(0.001, t + duration);
    source.connect(filter).connect(gain).connect(this.master);
    source.start(t, Math.random());
    source.stop(t + duration + 0.05);
  }

  flap(strength) {
    this.burst(0.3, 900, 180, 0.35 * strength);
  }

  splash() {
    this.burst(1.2, 2500, 200, 0.7);
  }

  thud() {
    this.burst(0.5, 400, 60, 0.8);
  }
}
