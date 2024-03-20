.. _installation:

Installation
==================

.. note::

    For Macs, macOS >= 10.15 is required to install SkyFlow.

To install Skyflow's python API and CLI, run:

.. code-block:: shell

    # Recommended: Create new conda env to avoid package conflicts.
    conda create -y -n skyflow python=3.10
    conda activate skyflow

    # Pull the latest version of SkyFlow from Github.
    git clone https://github.com/michaelzhiluo/skyflow.git

    # Install basic SkyFlow dependencies.
    cd skyflow
    pip install -e .


To install dependencies for the API server, run:

.. code-block:: shell

    # Recommended: Create new conda env to avoid package conflicts.
    conda create -y -n skyflow python=3.10å
    conda activate skyflow

    # Pull the latest version of SkyFlow from Github.
    git clone https://github.com/michaelzhiluo/skyflow.git

    # Install API server dependencies.
    cd skyflow
    pip install -e .[server]
