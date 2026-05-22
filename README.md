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
Once your DTaaS workspace is running, open your terminal (or VNC session) and and run below command in terminal.
```bash
cd /workspace/digital_twins/solar-panel
chmod +x ./lifecycle/*
./lifecycle/create
./lifecycle/execute
```
To terminate the digital twin, run below command in same directory
```bash
./lifecycle/terminate
```




### 📊 Interacting with the Twin
Open your browser to **`http://localhost:5173`** (or other as mentioned on terminal) to interact with the Digital Twin dashboard. 

* **Forward Mode:** Manually adjust the Pan and Tilt to see the mock physical hardware react and report power.
* **Inverse Mode (AI):** Set a target power, and the Python Optimizer will automatically calculate and execute the best orientation.