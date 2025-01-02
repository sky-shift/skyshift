#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR=$(dirname "$0")

# Change to the script's directory
cd "$SCRIPT_DIR"

# Remove the build and docs directories
rm -rf build

# Execute make html command
make html

# Check if the --serve flag is passed
if [[ "$1" == "--serve" ]]; then
  # Run the server for docs
  cd build/html
  python3 -m http.server 8000
else
  echo "Build complete. Use --serve to start a local server."
fi