# DTaaS & Solar Panel Digital Twin

This repository contains the deployment configuration for the Digital Twin as a Service (DTaaS) platform and a bi-directional Hardware-in-the-Loop (HiL) Solar Panel Digital Twin. 

The Digital Twin uses a 4-tier microservices architecture (React Frontend ↔ Node.js Gateway ↔ Python FMU Models ↔ Hardware Mock) to ensure stability and bypass high-latency network drops.

---

## PART 1: DTaaS Local Environment Setup (Ubuntu)

### 📋 Prerequisites
* Docker and Docker Compose v28+ installed.
* An active GitLab account for authorization.

### 🛠️ 1. Initial Fix for Ubuntu Docker (If Needed)
If Docker throws an error regarding `docker-credential-desktop` (a common issue on native Ubuntu), clear the invalid configuration before starting:
```bash
mv ~/.docker/config.json ~/.docker/config.json.bak
```

### 🚀 2. Installation & Configuration

**Step A: Clone the Repository**
```bash
git clone [https://github.com/INTO-CPS-Association/DTaaS.git](https://github.com/INTO-CPS-Association/DTaaS.git)
cd DTaaS
```

**Step B: Configure the Environment**
Open the local environment file:
```bash
nano deploy/docker/.env.local
```
Ensure the following variables are set to your absolute path and GitLab username:
```text
DTAAS_DIR='/home/tanaysheth/Desktop/DTaaS'
username1='tanaysheth0108'
```

**Step C: Create the User Workspace**
Copy the default template to create your personal workspace directory:
```bash
cp -R files/user1 files/tanaysheth0108
```

### 🟢 3. Running the Platform

To start the DTaaS microservices in the background, run this from the root `DTaaS` directory:
```bash
docker compose -f deploy/docker/compose.local.yml --env-file deploy/docker/.env.local up -d
```

**Accessing the Web Client:**
Once the containers are running, open your web browser and navigate to:
👉 `http://localhost`

You will be prompted to log in using your GitLab credentials.

### 🔴 4. Stopping the Platform

When you are done working and want to shut down the containers to free up system resources, run:
```bash
docker compose -f deploy/docker/compose.local.yml --env-file deploy/docker/.env.local down
```

### 💡 Important Notes & Useful Commands

* **Restarting a single service:** If the web client gets stuck, you can restart just that container without taking down the whole system:
  ```bash
  docker compose -f deploy/docker/compose.local.yml --env-file deploy/docker/.env.local up -d --force-recreate client
  ```
* **Localhost Limitations:** This specific local configuration does not spin up the "library microservice." You will need to manage and store your digital twin assets directly within your `/files/tanaysheth0108` workspace folder.

---

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