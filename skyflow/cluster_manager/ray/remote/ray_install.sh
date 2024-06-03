#!/bin/bash
# TODO(alex), supposrt for different OS distributions.

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

# Create a new environment called 'SkyShift'
echo "Creating new environment 'SkyShift'..."
conda create -y -n SkyShift python=3.10

# Activate the environment
source "$MINICONDA_INSTALL_DIR/bin/activate" SkyShift

# Install Ray in the environment via pip
echo "Installing Ray..."
pip install ray[all]

# Calculate recommended shared memory size
total_memory=$(free | awk '/^Mem:/ {print $2 * 1024}')
recommended_shm_size=$(awk -v mem=$total_memory 'BEGIN {printf "%d", mem * 0.3}')

# Start Ray with the specified options
echo "Starting Ray with 30% of total memory for object store..."
ray start --head --port=6379 \
    --dashboard-host=0.0.0.0 \
    --object-store-memory=$recommended_shm_size

echo "Ray has been started with the recommended shared memory size."
