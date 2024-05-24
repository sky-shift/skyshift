#!/bin/bash

# Function to detect the package manager
detect_package_manager() {
    if command -v apt-get &> /dev/null; then
        echo "apt-get"
    elif command -v yum &> /dev/null; then
        echo "yum"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    else
        echo "unsupported"
    fi
}

# Install necessary dependencies
install_dependencies() {
    PACKAGE_MANAGER=$(detect_package_manager)

    case $PACKAGE_MANAGER in
        "apt-get")
            sudo apt-get update
            sudo apt-get install -y wget bzip2
            ;;
        "yum")
            sudo yum install -y wget bzip2
            ;;
        "dnf")
            sudo dnf install -y wget bzip2
            ;;
        "zypper")
            sudo zypper install -y wget bzip2
            ;;
        "pacman")
            sudo pacman -Syu --noconfirm wget bzip2
            ;;
        *)
            echo "Unsupported package manager. Please install wget and bzip2 manually."
            exit 1
            ;;
    esac
}

# Download and install Miniconda
install_miniconda() {
    # Define Miniconda URL and install script
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    INSTALL_SCRIPT="Miniconda3-latest-Linux-x86_64.sh"

    # Download the Miniconda installer
    wget $MINICONDA_URL -O $INSTALL_SCRIPT

    # Verify the download
    wget $MINICONDA_URL.sha256 -O $INSTALL_SCRIPT.sha256
    sha256sum -c $INSTALL_SCRIPT.sha256

    # Make the installer executable
    chmod +x $INSTALL_SCRIPT

    # Run the installer
    ./$INSTALL_SCRIPT -b -p $HOME/miniconda

    # Initialize Miniconda
    $HOME/miniconda/bin/conda init

    # Cleanup
    rm $INSTALL_SCRIPT
}

# Main function
main() {
    install_dependencies
    install_miniconda

    echo "Miniconda installation is complete. Please restart your terminal or source the shell profile script to use conda."
}

# Execute the main function
main
