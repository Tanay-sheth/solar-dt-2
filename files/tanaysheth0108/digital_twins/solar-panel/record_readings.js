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
  transports: ['polling', 'websocket'],
  reconnection: true,
});

let sampleCount = 0;

socket.on('connect', () => {
  console.log(`Connected to Gateway (Socket ID: ${socket.id})`);
  console.log(`Recording live power readings to: ${CSV_FILE}`);
  console.log(`Press Ctrl+C to stop recording.\n`);
});

socket.on('disconnect', () => {
  console.log('Disconnected from Gateway. Waiting for reconnection...');
});

socket.on('connect_error', (err) => {
  console.error(`Connection error: ${err.message}. Retrying...`);
});

socket.on('telemetry_update', (payload) => {
  if (!payload || typeof payload.current_power !== 'number') {
    return;
  }

  const power = Number(payload.current_power.toFixed(4));
  const time = new Date().toISOString();

  const line = `${time},${power}\n`;
  fs.appendFileSync(CSV_FILE, line, 'utf8');
  sampleCount++;

  console.log(`[${new Date().toLocaleTimeString()}] Sample #${sampleCount} | Time: ${time} | Power: ${power.toFixed(4)} W`);
});

// Handle graceful exit
process.on('SIGINT', () => {
  console.log(`\n\nRecording stopped.`);
  console.log(`Total samples saved: ${sampleCount}`);
  console.log(`Saved to: ${CSV_FILE}`);
  process.exit(0);
});

