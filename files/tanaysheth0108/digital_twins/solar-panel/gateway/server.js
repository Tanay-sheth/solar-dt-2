const express = require('express');
const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const { Server } = require('socket.io');

const CSV_FILE = path.resolve(__dirname, '..', 'power_readings.csv');
const OPTIMAL_CSV_FILE = path.resolve(__dirname, '..', 'optimal_power_readings.csv');
const CYCLE_INTERVAL_MS = (Number(process.env.CSV_INTERVAL_MINUTES) || 20) * 60 * 1000; // 20 minutes
let lastCycleTime = 0;
let mpptRunning = false;
let latestPower = 0.0;

function getIstTimestamp() {
  const d = new Date();
  return d.toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata' }).replace(' ', 'T') + '+05:30';
}

function appendFlatReadingToCsv(power) {
  try {
    if (!fs.existsSync(CSV_FILE)) {
      fs.writeFileSync(CSV_FILE, 'time,power\n', 'utf8');
    } else {
      const content = fs.readFileSync(CSV_FILE, 'utf8');
      if (content.length > 0 && !content.endsWith('\n')) {
        fs.appendFileSync(CSV_FILE, '\n', 'utf8');
      }
    }
    const timestamp = getIstTimestamp();
    const row = `${timestamp},${Number(power).toFixed(4)}\n`;
    fs.appendFileSync(CSV_FILE, row, 'utf8');
    console.log(`[Flat CSV] Logged reading at ${timestamp}: ${Number(power).toFixed(4)} W at (0, 0)`);
  } catch (err) {
    console.error('Failed to append flat reading to CSV:', err.message);
  }
}

function appendOptimalReadingToCsv(pan, tilt, power) {
  try {
    if (!fs.existsSync(OPTIMAL_CSV_FILE)) {
      fs.writeFileSync(OPTIMAL_CSV_FILE, 'time,pan,tilt,power\n', 'utf8');
    } else {
      const content = fs.readFileSync(OPTIMAL_CSV_FILE, 'utf8');
      if (content.length > 0 && !content.endsWith('\n')) {
        fs.appendFileSync(OPTIMAL_CSV_FILE, '\n', 'utf8');
      }
    }
    const timestamp = getIstTimestamp();
    const row = `${timestamp},${Number(pan).toFixed(1)},${Number(tilt).toFixed(1)},${Number(power).toFixed(4)}\n`;
    fs.appendFileSync(OPTIMAL_CSV_FILE, row, 'utf8');
    console.log(`[Optimal CSV] Logged reading at ${timestamp}: Pan ${Number(pan).toFixed(1)}°, Tilt ${Number(tilt).toFixed(1)}°, Power ${Number(power).toFixed(4)} W`);
  } catch (err) {
    console.error('Failed to append optimal reading to CSV:', err.message);
  }
}

const WS_PORT = 4000;
const TCP_PORT = 4001;
const HARDWARE_TX_DELAY_MS = Math.max(0, Number(process.env.HARDWARE_TX_DELAY_MS || 0));
const HARDWARE_RX_DELAY_MS = Math.max(0, Number(process.env.HARDWARE_RX_DELAY_MS || 0));

function parsePowerFrame(line) {
  const text = line.trim();
  const match = text.match(/^>P:([-+]?\d*\.?\d+)$/);
  if (!match) {
    return null;
  }

  const value = Number(match[1]);
  if (Number.isNaN(value)) {
    return null;
  }

  return value;
}

class MockTcpHardwareClient {
  constructor() {
    this.socket = null;
    this.buffer = '';
    this.onDataHandler = null;
  }

  attachSocket(socket) {
    this.socket = socket;
    this.buffer = '';

    socket.on('data', (chunk) => {
      this.buffer += chunk.toString('utf8');
      while (this.buffer.includes('\n')) {
        const idx = this.buffer.indexOf('\n');
        const line = this.buffer.slice(0, idx);
        this.buffer = this.buffer.slice(idx + 1);
        if (this.onDataHandler) {
          this.onDataHandler(line);
        }
      }
    });

    socket.on('close', () => {
      if (this.socket === socket) {
        this.socket = null;
        this.buffer = '';
      }
      console.log('Hardware client disconnected');
    });

    socket.on('error', (error) => {
      console.error('Hardware socket error:', error.message);
    });
  }

  write(frame) {
    if (!this.socket || this.socket.destroyed) {
      return;
    }

    if (HARDWARE_TX_DELAY_MS > 0) {
      setTimeout(() => {
        if (!this.socket || this.socket.destroyed) {
          return;
        }
        this.socket.write(frame);
      }, HARDWARE_TX_DELAY_MS);
      return;
    }

    this.socket.write(frame);
  }

  onData(handler) {
    this.onDataHandler = handler;
  }
}

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" },
  transports: ["polling", "websocket"], // Allow both
  pingTimeout: 120000,  // 2 minutes (vital for hotspots)
  pingInterval: 30000,
  connectTimeout: 45000
});

let activeControlMode = 'forward';
let manualSetpoint = { pan: 0, tilt: 0 };

// ── 2-D Perturb & Observe MPPT Engine ──────────────────────────────────────
const _PAN_MIN = -90, _PAN_MAX = 90;
const _TILT_MIN = -90, _TILT_MAX = 90;
const _STEP_INIT = 10.0;
const _STEP_MIN = 0.5;
const _STEP_SHRINK = 0.65;
const _POWER_TOL = 0.00025;

async function probePose(pan, tilt) {
  pan = Math.max(_PAN_MIN, Math.min(_PAN_MAX, Math.round(pan * 10) / 10));
  tilt = Math.max(_TILT_MIN, Math.min(_TILT_MAX, Math.round(tilt * 10) / 10));

  hardwareClient.write(`<${pan},${tilt}>\n`);
  io.emit('model_update', { target_pan: pan, target_tilt: tilt, state: 'PROBING' });

  // Wait 1400ms for hardware travel + INA219 reading
  await new Promise((resolve) => setTimeout(resolve, 1400));
  return { pan, tilt, power: latestPower };
}

async function runMpptSearch() {
  console.log('\n[MPPT] Starting 2-D Perturb & Observe MPPT search...');
  io.emit('model_update', { state: 'MPPT_START' });

  let bestPan = 0;
  let bestTilt = 0;
  let start = await probePose(0, 0);
  let bestPower = start.power;
  let step = _STEP_INIT;

  console.log(`[MPPT] Center power at (0, 0): ${bestPower.toFixed(4)} W`);

  while (step >= _STEP_MIN) {
    const cardinalDeltas = [
      { dPan: step, dTilt: 0 },
      { dPan: -step, dTilt: 0 },
      { dPan: 0, dTilt: step },
      { dPan: 0, dTilt: -step },
    ];

    let roundBest = { pan: bestPan, tilt: bestTilt, power: -1 };

    for (const delta of cardinalDeltas) {
      const pPan = Math.max(_PAN_MIN, Math.min(_PAN_MAX, bestPan + delta.dPan));
      const pTilt = Math.max(_TILT_MIN, Math.min(_TILT_MAX, bestTilt + delta.dTilt));

      if (Math.abs(pPan - bestPan) < 0.1 && Math.abs(pTilt - bestTilt) < 0.1) {
        continue;
      }

      const res = await probePose(pPan, pTilt);
      console.log(`  [Probe] Pan: ${res.pan}°, Tilt: ${res.tilt}°, Power: ${res.power.toFixed(4)} W`);
      if (res.power > roundBest.power) {
        roundBest = res;
      }
    }

    if (roundBest.power > bestPower + _POWER_TOL) {
      bestPan = roundBest.pan;
      bestTilt = roundBest.tilt;
      bestPower = roundBest.power;
      console.log(`[MPPT Step] -> Improved! Best: (${bestPan}°, ${bestTilt}°), Power: ${bestPower.toFixed(4)} W (Step: ${step.toFixed(1)}°)`);
    } else {
      step *= _STEP_SHRINK;
      console.log(`[MPPT Step] -> Shrinking step to ${step.toFixed(2)}°`);
    }
  }

  // Move to converged MPP pose
  const mpp = await probePose(bestPan, bestTilt);
  console.log(`[MPPT DONE] Maximum Power Point found: Pan=${bestPan}°, Tilt=${bestTilt}°, Power=${mpp.power.toFixed(4)} W`);

  // Log optimal reading to optimal_power_readings.csv
  appendOptimalReadingToCsv(bestPan, bestTilt, mpp.power);

  io.emit('model_update', {
    target_pan: bestPan,
    target_tilt: bestTilt,
    estimated_max_power: mpp.power,
    state: 'MPPT_DONE'
  });

  // Hold at optimal pose for 5 seconds
  await new Promise((resolve) => setTimeout(resolve, 5000));

  // Return panel to (0, 0) flat
  console.log('[MPPT] Returning panel to flat (0, 0)...');
  await probePose(0, 0);
  io.emit('model_update', { target_pan: 0, target_tilt: 0, state: 'IDLE' });
  console.log(`[MPPT] Panel is at (0, 0). Next measurement cycle in 20 minutes.\n`);
}

async function runCycle() {
  if (mpptRunning) return;
  mpptRunning = true;
  try {
    // 1. Log flat reading at (0, 0)
    appendFlatReadingToCsv(latestPower);

    // 2. Run MPPT search to find optimal angle & power
    await runMpptSearch();
  } catch (err) {
    console.error('[Cycle Error]:', err.message);
  } finally {
    mpptRunning = false;
  }
}

function checkCycleTrigger() {
  if (mpptRunning || activeControlMode !== 'forward') return;
  const now = Date.now();
  if (now - lastCycleTime >= CYCLE_INTERVAL_MS) {
    lastCycleTime = now;
    runCycle();
  }
}

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

app.get('/trigger-cycle', (_req, res) => {
  if (mpptRunning) {
    return res.json({ status: 'in_progress', message: 'Measurement cycle is currently running' });
  }
  runCycle();
  res.json({ status: 'started', message: 'Triggered 20-min cycle (flat reading + MPPT search)' });
});

const hardwareClient = new MockTcpHardwareClient();
hardwareClient.onData((line) => {
  const power = parsePowerFrame(line);
  if (power === null) {
    return;
  }

  latestPower = power;
  checkCycleTrigger();

  const emitTelemetry = () => {
    io.emit('telemetry_update', { current_power: power });
  };

  if (HARDWARE_RX_DELAY_MS > 0) {
    setTimeout(emitTelemetry, HARDWARE_RX_DELAY_MS);
    return;
  }

  emitTelemetry();
});

const tcpServer = net.createServer((socket) => {
  console.log(`Hardware connected from ${socket.remoteAddress}:${socket.remotePort}`);
  hardwareClient.attachSocket(socket);
});

tcpServer.listen(TCP_PORT, () => {
  console.log(`Gateway TCP hardware server listening on port ${TCP_PORT}`);
});

/*
Hardware swap (TCP mock -> real Arduino with serialport):
1) Remove the net.createServer block above.
2) Install serialport: npm install serialport
3) Open a serial port and bridge bytes to/from hardwareClient logic.

Example outline:
const { SerialPort } = require('serialport');
const serial = new SerialPort({ path: '/dev/ttyUSB0', baudRate: 115200 });
serial.on('data', (chunk) => { ...same line-buffer parsing... });
hardwareClient.write = (frame) => serial.write(frame);
*/

io.on('connection', (socket) => {
  console.log(`Socket.io client connected: ${socket.id}`);

  socket.emit('control_mode', { mode: activeControlMode });

  socket.on('control_mode', (payload) => {
    const nextMode = payload && payload.mode === 'inverse' ? 'inverse' : 'forward';
    activeControlMode = nextMode;
    io.emit('control_mode', { mode: activeControlMode });

    if (activeControlMode === 'forward') {
      const frame = `<${manualSetpoint.pan},${manualSetpoint.tilt}>\n`;
      hardwareClient.write(frame);
    }
  });

  socket.on('set_angles', (payload) => {
    if (!payload || typeof payload.pan !== 'number' || typeof payload.tilt !== 'number') {
      return;
    }

    if (activeControlMode !== 'forward') {
      activeControlMode = 'forward';
      io.emit('control_mode', { mode: activeControlMode });
    }

    manualSetpoint = {
      pan: Number(payload.pan),
      tilt: Number(payload.tilt),
    };

    const frame = `<${payload.pan},${payload.tilt}>\n`;
    hardwareClient.write(frame);
  });

  socket.on('update_target_power', (payload) => {
    const rawTarget = payload && typeof payload.target === 'number' ? payload.target : null;
    if (rawTarget === null || Number.isNaN(rawTarget)) {
      return;
    }

    if (activeControlMode !== 'inverse') {
      activeControlMode = 'inverse';
      io.emit('control_mode', { mode: activeControlMode });
    }

    const target = Number(rawTarget);
    io.emit('update_target_power', { target });
  });

  // Backward compatibility with older emitter name.
  socket.on('set_target_power', (payload) => {
    const rawTarget = payload && typeof payload.target === 'number' ? payload.target : null;
    if (rawTarget === null || Number.isNaN(rawTarget)) {
      return;
    }

    if (activeControlMode !== 'inverse') {
      activeControlMode = 'inverse';
      io.emit('control_mode', { mode: activeControlMode });
    }

    const target = Number(rawTarget);
    io.emit('update_target_power', { target });
  });

  socket.on('model_update', (payload) => {
    if (!payload || typeof payload !== 'object') {
      return;
    }

    const pan = typeof payload.target_pan === 'number' ? payload.target_pan : null;
    const tilt = typeof payload.target_tilt === 'number' ? payload.target_tilt : null;
    const achievable = payload.achievable === false ? false : true;

    const update = {
      target_pan: pan,
      target_tilt: tilt,
      achievable,
    };

    io.emit('model_update', update);
    io.emit('optimization_result', update);

    if (activeControlMode === 'inverse' && pan !== null && tilt !== null) {
      const frame = `<${pan},${tilt}>\n`;
      hardwareClient.write(frame);
    }
  });

  socket.on('disconnect', () => {
    console.log(`Socket.io client disconnected: ${socket.id}`);
  });
});

server.listen(WS_PORT, () => {
  console.log(`Gateway Socket.io server listening on port ${WS_PORT}`);
});

setInterval(() => {
  if (activeControlMode !== 'forward' || mpptRunning) {
    return;
  }

  const frame = `<${manualSetpoint.pan},${manualSetpoint.tilt}>\n`;
  hardwareClient.write(frame);
}, 1000);
