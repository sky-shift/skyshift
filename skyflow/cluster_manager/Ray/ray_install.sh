#!/bin/bash

# Function to check if conda is installed
check_conda_installed() {
    if ! command -v conda &> /dev/null; then
        echo "Conda is not installed. Please install Miniconda or Anaconda first."
        exit 1
    fi
}

# Function to create a new conda environment with Python 3.10
create_conda_environment() {
    ENV_NAME=$1

    conda create -n $ENV_NAME python=3.10 -y
}

# Function to install ray[all] using pip in the conda environment
install_ray() {
    ENV_NAME=$1

    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate $ENV_NAME
    pip install ray[all]
    conda deactivate
}

# Main function
main() {
    ENV_NAME="my_ray_env"  # You can change the environment name here

    check_conda_installed
    create_conda_environment $ENV_NAME
    install_ray $ENV_NAME

    echo "Conda environment '$ENV_NAME' with Python 3.10 and ray[all] installed successfully."
}

# Execute the main function
main
