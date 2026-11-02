const fs = require('fs');
const path = require('path');

// Resolve socket.io-client from gateway/node_modules or local
let io;
try {
  io = require('socket.io-client');
} catch (e) {
  io = require(path.join(__dirname, 'gateway', 'node_modules', 'socket.io-client'));
}

// Config
const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:4000';
const CSV_FILE = process.argv[2] || path.join(__dirname, 'power_readings.csv');

// Initialize CSV with header if file does not exist
if (!fs.existsSync(CSV_FILE)) {
  fs.writeFileSync(CSV_FILE, 'time,power\n', 'utf8');
  console.log(`Created new CSV file: ${CSV_FILE}`);
} else {
  console.log(`Appending to existing CSV file: ${CSV_FILE}`);
}

console.log(`Connecting to Gateway at ${GATEWAY_URL}...`);
const socket = io(GATEWAY_URL, {
  transports: ['polling'],
  reconnection: true,
});

const INTERVAL_MS = (Number(process.env.INTERVAL_MINUTES) || 20) * 60 * 1000; // 20 minutes
let sampleCount = 0;
let lastLogTime = 0;

socket.on('connect', () => {
  console.log(`Connected to Gateway (Socket ID: ${socket.id})`);
  console.log(`Recording live power readings every 20 minutes to: ${CSV_FILE}`);
  console.log(`Press Ctrl+C to stop recording.\n`);
});

socket.on('disconnect', () => {
  console.log('Disconnected from Gateway. Waiting for reconnection...');
});

socket.on('connect_error', (err) => {
  console.error(`Connection error: ${err.message}. Retrying...`);
});

function getIstTimestamp() {
  const d = new Date();
  return d.toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata' }).replace(' ', 'T') + '+05:30';
}

socket.on('telemetry_update', (payload) => {
  if (!payload || typeof payload.current_power !== 'number') {
    return;
  }

  const now = Date.now();
  // Only log if 20 minutes have passed since last log (first sample logs immediately)
  if (now - lastLogTime < INTERVAL_MS) {
    return;
  }
  lastLogTime = now;

  const power = Number(payload.current_power.toFixed(4));
  const time = getIstTimestamp();

  // Ensure file ends with newline before appending
  if (fs.existsSync(CSV_FILE)) {
    const content = fs.readFileSync(CSV_FILE, 'utf8');
    if (content.length > 0 && !content.endsWith('\n')) {
      fs.appendFileSync(CSV_FILE, '\n', 'utf8');
    }
  }

  const line = `${time},${power.toFixed(4)}\n`;
  fs.appendFileSync(CSV_FILE, line, 'utf8');
  sampleCount++;

  console.log(`[${time}] Sample #${sampleCount} | Power: ${power.toFixed(4)} W (Next log in 20 min)`);
});

// Handle graceful exit
process.on('SIGINT', () => {
  console.log(`\n\nRecording stopped.`);
  console.log(`Total samples saved: ${sampleCount}`);
  console.log(`Saved to: ${CSV_FILE}`);
  process.exit(0);
});

