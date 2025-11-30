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
