#!/bin/bash

# Directory where Miniconda will be installed
MINICONDA_INSTALL_DIR="$HOME/miniconda3"

# Check if Miniconda is already installed
if [ ! -d "$MINICONDA_INSTALL_DIR" ]; then
    echo "Miniconda not found. Installing Miniconda..."
    
    # Download Miniconda installer
    curl -o Miniconda3-latest-Linux-x86_64.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    
    # Make installer executable
    chmod +x Miniconda3-latest-Linux-x86_64.sh
    
    # Install Miniconda
    ./Miniconda3-latest-Linux-x86_64.sh -b -p $MINICONDA_INSTALL_DIR
    
    # Remove installer
    rm Miniconda3-latest-Linux-x86_64.sh
else
    echo "Miniconda is already installed."
fi

# Add Miniconda to PATH temporarily for this script
export PATH="$MINICONDA_INSTALL_DIR/bin:$PATH"

# Update conda
conda update -y conda

# Create a new environment called 'skyflow'
echo "Creating new environment 'skyflow'..."
conda create -y -n skyflow python=3.10

# Activate the environment
source "$MINICONDA_INSTALL_DIR/bin/activate" skyflow

# Install Ray in the environment via pip
echo "Installing Ray..."
pip install ray[all]

# Calculate recommended shared memory size
recommended_shm_size=$(free | awk '/^Mem:/ {print $2}')

# Start Ray with the specified options
echo "Starting Ray..."
ray start --head --port=6379 \
    --dashboard-host=0.0.0.0 \
    --object-store-memory=$recommended_shm_size

echo "Ray has been started with the recommended shared memory size."
