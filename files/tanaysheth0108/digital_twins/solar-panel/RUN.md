# Solar Panel Digital Twin - Execution Guide

This project is optimized for the **BITS Goa DTaaS environment** and **Mobile Hotspot** connectivity. 
It uses a Microservices architecture (Python + Node.js) to bypass GLIBC and WebSocket latency issues.

## 1. Quick Environment Setup
If this is a fresh terminal session, run these once:
'''bash
pip install "python-socketio[client]" requests eventlet
cd gateway && npm install && cd ../frontend && npm install && cd ..
'''

## 2. The "One-Command" Launch
'''bash
# --- CLEANUP ---
fuser -k 4000/tcp 4001/tcp 5173/tcp || true
pkill -f "hardware_proxy.py" || true
pkill -f "optimizer.py" || true
pkill -f "mock_panel.py" || true

# --- EXECUTION ---
# 1. Start Gateway (The Heart)
node gateway/server.js > gateway.log 2>&1 &
sleep 3

# 2. Start Frontend (The UI)
cd frontend && nohup npm run dev > /dev/null 2>&1 &
cd ..
sleep 5

# 3. Start Hardware Mock (The Physical Body)
python3 hardware/mock_panel.py > mock.log 2>&1 &
sleep 2

# 4. Start Digital Twins (The Brains)
python3 models/hardware_proxy.py > proxy.log 2>&1 &
python3 models/optimizer.py > optimizer.log 2>&1 &

echo "🚀 All systems launched!"
echo "Dashboard: http://localhost:5173"
'''

3. Recommended: Tabbed DebuggingFor a lab environment, it is better to run these in 4 separate tabs to monitor the logs:TabComponentCommand
1 Gateway node gateway/server.js
2 Frontendcd frontend && npm run dev
3 Hardwarepython3 hardware/mock_panel.py
4 Twinspython3 models/optimizer.py & python3 models/hardware_proxy.py