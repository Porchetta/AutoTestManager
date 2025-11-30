#!/bin/bash

ENV_NAME="mss-test-manager"

echo "Creating Conda environment '$ENV_NAME' with Python 3.10..."
conda create -n $ENV_NAME python=3.10 -y

echo "Installing backend dependencies..."
# We use conda run to execute pip inside the environment without activating it in the shell
conda run -n $ENV_NAME pip install -r backend/requirements.txt

echo "Setup complete! You can now run ./dev.sh"
