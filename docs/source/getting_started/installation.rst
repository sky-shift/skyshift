.. _installation:

Installation
==================

.. note::

    For Macs, macOS >= 10.15 is required to install SkyShift. Apple Silicon-based devices (e.g. Apple M1) must run ``pip uninstall grpcio; conda install -c conda-forge grpcio=1.43.0`` prior to installing SkyShift.

Prerequisites
------------

SkyShift requires SkyPilot to be installed and configured with at least one cloud provider. Follow these steps to set up your environment:

1. Install SkyPilot with your preferred cloud provider(s):

.. code-block:: shell

    # Recommended: use a new conda env to avoid package conflicts.
    # SkyPilot requires 3.7 <= python <= 3.11.
    conda create -y -n skyshift python=3.10
    conda activate skyshift

    # Choose your cloud provider(s):
    pip install "skypilot[aws]==0.5.0"     # For AWS
    pip install "skypilot[gcp]==0.5.0"     # For Google Cloud
    pip install "skypilot[azure]==0.5.0"   # For Azure
    pip install "skypilot[all]==0.5.0"     # For all supported clouds

    # Verify cloud access is properly configured
    sky check

2. Install SkyShift:

.. code-block:: shell

    # Pull the latest version of SkyShift
    git clone https://github.com/sky-shift/skyshift.git
    cd skyshift

    # For basic usage (CLI and Python API)
    pip install -e .

    # For API server deployment
    pip install -e .[server]

    # For development
    pip install -e .[dev]

Docker Installation
-----------------

As a quick alternative, we provide a Docker image with SkyShift and its dependencies pre-installed:

.. code-block:: shell

    # NOTE: '--platform linux/amd64' is needed for Apple silicon Macs
    docker run --platform linux/amd64 \\
      -td --rm --name skyshift \\
      -v "$HOME/.sky:/root/.sky:rw" \\
      -v "$HOME/.aws:/root/.aws:rw" \\
      -v "$HOME/.config/gcloud:/root/.config/gcloud:rw" \\
      skyshift/skyshift:latest

    docker exec -it skyshift /bin/bash

Cloud Setup
----------

If you haven't configured your cloud credentials yet, follow the SkyPilot cloud setup guides:

- `AWS Setup Guide <https://skypilot.readthedocs.io/en/latest/getting-started/installation.html#amazon-web-services-aws>`_
- `GCP Setup Guide <https://skypilot.readthedocs.io/en/latest/getting-started/installation.html#google-cloud-platform-gcp>`_
- `Azure Setup Guide <https://skypilot.readthedocs.io/en/latest/getting-started/installation.html#azure>`_

After configuring your cloud credentials, verify the setup:

.. code-block:: shell

    sky check

This will show which clouds are properly configured and available for use with SkyShift.
