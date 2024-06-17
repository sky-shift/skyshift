#!/bin/bash
# TODO(alex): support for different OS distributions.

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

# Check if the 'skyshift' environment already exists
if conda env list | grep -q 'skyshift'; then
    echo "The 'skyshift' environment already exists. Checking for Ray installation..."
    
    # Activate the environment
    source "$MINICONDA_INSTALL_DIR/bin/activate" skyshift
    
    # Check if Ray is installed
    if ! pip show ray > /dev/null 2>&1; then
        echo "Ray is not installed. Reinstalling the environment..."
        
        # Deactivate the environment
        conda deactivate
        
        # Remove the existing environment
        conda env remove -n skyshift
        
        # Recreate the environment
        conda create -y -n skyshift python=3.10
        source "$MINICONDA_INSTALL_DIR/bin/activate" skyshift
        
        # Install Ray
        echo "Installing Ray..."
        pip install ray[all]
    else
        echo "Ray is already installed."
    fi
else
    echo "Creating new environment 'skyshift'..."
    conda create -y -n skyshift python=3.10
    
    # Activate the environment
    source "$MINICONDA_INSTALL_DIR/bin/activate" skyshift
    
    # Install Ray
    echo "Installing Ray..."
    pip install ray[all]
fi

conda activate skyshift

# Calculate recommended shared memory size
total_memory=$(free | awk '/^Mem:/ {print $2 * 1024}')
recommended_shm_size=$(awk -v mem=$total_memory 'BEGIN {printf "%d", mem * 0.3}')
    
# Start Ray with the specified options
echo "Starting Ray with 30% of total memory for object store..."
ray start --head --port=6379 \
    --dashboard-host=0.0.0.0 \
    --dashboard-port=8265 \
    --object-store-memory=$recommended_shm_size
    
echo "Ray has been started with the recommended shared memory size."