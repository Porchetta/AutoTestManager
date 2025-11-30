#!/bin/bash

# 1. Stop existing containers but keep DB running
echo "Stopping Backend and Frontend containers..."
docker-compose stop backend frontend
docker-compose up -d db

# Wait for DB
echo "Waiting for DB..."
sleep 5

# 2. Install Backend Dependencies & Run
echo "Starting Backend (Local)..."
cd backend
# Run uvicorn using the conda environment
conda run --no-capture-output -n mss-test-manager uvicorn app.main:app --reload --port 40223 &
BACKEND_PID=$!
cd ..

# 3. Install Frontend Dependencies & Run
echo "Starting Frontend (Local)..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Development Environment Started!"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Press CTRL+C to stop both."

# Trap CTRL+C to kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
