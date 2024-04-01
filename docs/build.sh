#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR=$(dirname "$0")

# Change to the script's directory
cd "$SCRIPT_DIR"

# Remove the build and docs directories
rm -rf build docs

# Execute make html command
make html

# Run the server for docs
cd build/html
python -m http.server 8000