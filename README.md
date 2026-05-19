## Quick Start

### 1. Create Configuration Files

```bash
cp config/.env.example config/.env
cp config/client.js.example config/client.js
```

### 2. Create User Workspace Directory

Edit `config/.env` and set `DEFAULT_USER`, then create a matching workspace:

```bash
cp -R files/template files/<DEFAULT_USER>
sudo chown -R 1000:100 files/*
```

### 3. Start Services

```bash
docker compose --env-file config/.env up -d
```

### 4. Open DTaaS

- <http://localhost>

Sign in using the configured OAuth provider in `config/client.js`
(default authority is `https://gitlab.com/`).

## Run

The commands to start and stop the application are:

```bash
docker compose --env-file config/.env up -d
docker compose --env-file config/.env down
```

## Notes

- This package does not include `libms` or backend forward-auth.
- For secure production deployments, see
  `deploy/dtaas/docker/secure-server`.

## Documentation

Please see
<https://into-cps-association.github.io/DTaaS/development/index.html>
for complete documentation.

## References

Image sources:
[Traefik logo](https://www.laub-home.de/wiki/Traefik_SSL_Reverse_Proxy_f%C3%BCr_Docker_Container),
[gitlab](https://gitlab.com)

## PART 2: Running the Solar Panel Digital Twin

### Master script
```bash
cd /workspace/digital_twins/solar-panel
chmod +x ./lifecycle/*
./lifecycle/create
./lifecycle/execute
./lifecycle/terminate
```

Once your DTaaS workspace is running, open your terminal (or VNC session) and start the 4 microservices in the exact order below. It is highly recommended to run these in **4 separate terminal tabs**.

### Tab 1: Start the Gateway (The Heart)
*Must be started first.*
```bash
cd /workspace/digital_twins/solar-panel
node gateway/server.js
```

### Tab 2: Start the Frontend (The UI)
```bash
cd /workspace/digital_twins/solar-panel/frontend
npm run dev
```
*(If you encounter a `SyntaxError: Unexpected token '??='` or need to upgrade Node.js first, run the following setup once:)*
```bash
conda deactivate
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm install --lts
nvm use --lts
nvm alias default 'lts/*'
node -v
which node
cd /workspace/digital_twins/solar-panel/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Tab 3: Start the Hardware Mock (The Physical Body)
```bash
cd /workspace/digital_twins/solar-panel
python3 hardware/mock_panel.py
```

### Tab 4: Start the Digital Twins (The Brains)
*This runs both the state proxy and the AI optimizer in the background.*
```bash
---------
cd /workspace/digital_twins/solar-panel
python3 -m venv venv
source venv/bin/activate
pip install pythonfmu
pip install python-socketio
pip install "python-socketio[client]"
----------
# when hardware configured
#    python3 models/hardware_proxy.py & python3 models/optimizer.py
```




### 📊 Interacting with the Twin
Once all 4 tabs are running without errors, open your browser to **`http://localhost:5173`** to interact with the Digital Twin dashboard. 

* **Forward Mode:** Manually adjust the Pan and Tilt to see the mock physical hardware react and report power.
* **Inverse Mode (AI):** Set a target power, and the Python Optimizer will automatically calculate and execute the best orientation.