# MSS Test Manager

A web-based platform for automating RTD and ezDFS test script execution.

## 🏗 Architecture

- **Frontend**: Vue 3 + Vite + Pinia (Port: 40203)
- **Backend**: FastAPI + SQLAlchemy (Port: 40223)
- **Database**: MySQL 8.0 (Port: 3306)
- **Infrastructure**: Docker Compose

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose installed.

### Installation & Run

1. **Clone the repository** (if not already done).
2. **Start the services**:
   ```bash
   docker-compose up --build -d
   ```
3. **Access the application**:
   - Frontend: [http://localhost:40203](http://localhost:40203)
   - Backend API Docs: [http://localhost:40223/docs](http://localhost:40223/docs)

### Offline run with prebuilt images
If you need to deploy on an offline environment, build and save the images on a machine with internet access, then load and run them offline.

1. **Build and tag images online**:
   ```bash
   docker compose build
   docker tag autotestmanager-frontend:latest mss-frontend:offline
   docker tag autotestmanager-backend:latest mss-backend:offline
   # mysql:8.0 is pulled automatically; save it too if the offline host lacks the image
   ```
2. **Save images to portable tarballs** (store them under `./images`):
   ```bash
   mkdir -p images
   docker save mss-frontend:offline -o images/frontend.tar
   docker save mss-backend:offline -o images/backend.tar
   docker save mysql:8.0 -o images/db.tar
   ```
3. **Transfer the repository and tarballs** to the offline host.
4. **Run the offline helper** (loads images and starts containers without rebuilding):
   ```bash
   ./offline-run.sh
   ```
   - Override tar locations or tags if needed:
     ```bash
     FRONTEND_TAR=/path/frontend.tar BACKEND_TAR=/path/backend.tar DB_TAR=/path/db.tar \
     FRONTEND_IMAGE=my-frontend:prod BACKEND_IMAGE=my-backend:prod DB_IMAGE=mysql:8.0 \
     ./offline-run.sh
     ```

### Offline build (no internet on the build host)
If you must also **build** in an offline environment, prefetch dependencies online, copy the `./offline` folder, then build without
network access.

1. **Prefetch online** (fills Python wheels + npm cache under `./offline`):
   ```bash
   ./offline-prep.sh
   ```
2. **Copy to the offline host**: transfer the repo and the generated `./offline` directory.
3. **Build offline using cached deps** (requires python+pip, node+npm, docker already installed offline):
   ```bash
   ./offline-build.sh
   ```
   - Installs backend deps from `offline/pip-wheels` via `pip install --no-index`.
   - Installs frontend deps from `offline/npm-cache` via `npm ci --offline`.
   - Builds both images with `--network=none` to ensure no internet is used.
4. **Run**: either `./offline-run.sh` (if you saved images) or `docker compose up -d` with the offline-built images.
   - The offline compose file (`docker-compose.offline.yml`) only uses prebuilt images—no source code is bind-mounted—so each image already contains the app code snapshot from the time you built it. Rebuild/tag fresh images if you change the backend or frontend source.

### Initial Login
- **Username**: `admin`
- **Password**: `admin123` (Note: Change this immediately after first login via My Page or Admin tools)

## 📂 Project Structure

```
/AutoTestManager
├── backend/            # FastAPI Application
│   ├── app/
│   │   ├── routers/    # API Endpoints (Auth, Admin, RTD, ezDFS)
│   │   ├── models.py   # DB Models
│   │   └── ...
│   └── Dockerfile
├── frontend/           # Vue 3 Application
│   ├── src/
│   │   ├── views/      # Page Components
│   │   ├── stores/     # Pinia State Management
│   │   └── ...
│   └── Dockerfile
├── database/           # Database Scripts
│   └── init.sql
└── docker-compose.yml
```

## 🧪 Features

- **RTD Test**: Step-by-step wizard for running RTD tests on specific lines.
- **ezDFS Test**: Select server and rule to run tests, with favorites support.
- **Admin Management**: Manage users (approve/promote) and system configurations.
- **My Page**: View history and change password.
