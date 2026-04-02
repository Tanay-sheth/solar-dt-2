# DTaaS Local Environment Setup Guide (Ubuntu)

This guide covers the steps to deploy the Digital Twin as a Service (DTaaS) platform locally using Docker. 

## 📋 Prerequisites
* Docker and Docker Compose v28+ installed.
* An active GitLab account for authorization.

---

## 🛠️ 1. Initial Fix for Ubuntu Docker (If Needed)
If Docker throws an error regarding `docker-credential-desktop` (a common issue on native Ubuntu), clear the invalid configuration before starting:
```bash
mv ~/.docker/config.json ~/.docker/config.json.bak
```

---

## 🚀 2. Installation & Configuration

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

---

## 🟢 3. Running the Platform

To start the DTaaS microservices in the background, run this from the root `DTaaS` directory:
```bash
docker compose -f deploy/docker/compose.local.yml --env-file deploy/docker/.env.local up -d
```

**Accessing the Web Client:**
Once the containers are running, open your web browser and navigate to:
👉 `http://localhost`

You will be prompted to log in using your GitLab credentials.

---

## 🔴 4. Stopping the Platform

When you are done working and want to shut down the containers to free up system resources, run:
```bash
docker compose -f deploy/docker/compose.local.yml --env-file deploy/docker/.env.local down
```

---

## 💡 Important Notes & Useful Commands

* **Restarting a single service:** If the web client gets stuck, you can restart just that container without taking down the whole system:
  ```bash
  docker compose -f deploy/docker/compose.local.yml --env-file deploy/docker/.env.local up -d --force-recreate client
  ```
* **Localhost Limitations:** This specific local configuration does not spin up the "library microservice." You will need to manage and store your digital twin assets directly within your `/files/tanaysheth0108` workspace folder.