# 🛠️ Local Development Setup Guide

## 1. Google Cloud SDK (Authentication)

The `gcloud` CLI is required to manage resources and verify configurations.

### **Login**
Run the following in PowerShell to authenticate:

```powershell
# 1. Login to your user account (opens browser)
gcloud auth login

# 2. Setup Application Default Credentials (ADC)
# This allows local scripts (like main.py) to access GCP services seamlessly.
gcloud auth application-default login --project <your-project-id>
```

### **Troubleshooting**
If you see `Python 3.9.x is no longer officially supported`, you can set the python interpreter manually:
```powershell
$env:CLOUDSDK_PYTHON = "path/to/python.exe"
```

---

## 2. Docker Desktop (Containerization)

Docker is required to run the `/preflight` container verification tests and build images locally.

### **Installation**
**Option A: Winget (Recommended)**
```powershell
winget install Docker.DockerDesktop
```

**Option B: Manual**
Download from [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop).

### **Post-Installation**
1. Search for **"Docker Desktop"** in the Start Menu and launch it.
2. Accept the terms.
3. Wait for the engine to start (the whale icon in system tray stops animating).
4. Verify in terminal:
   ```bash
   docker run hello-world
   ```

---

## 3. Verification

Once installed, run the project preflight check:

```bash
./scripts/preflight.sh
```
It should now pass all checks (Environment, GCP, Docker, and Code).
