.. _installation:

Installation
==================

.. note::

    For Macs, macOS >= 10.15 is required to install SkyShift.

To install SkyShift's python API and CLI, run:

.. code-block:: shell

    # Recommended: Create new conda env to avoid package conflicts.
    conda create -y -n skyshift python=3.10
    conda activate skyshift

    # Pull the latest version of SkyShift from Github.
    git clone https://github.com/michaelzhiluo/skyshift.git

    # Install basic SkyShift dependencies.
    cd skyshift
    pip install -e .


To install dependencies for the API server, run:

.. code-block:: shell

    # Recommended: Create new conda env to avoid package conflicts.
    conda create -y -n skyshift python=3.10
    conda activate skyshift

    # Pull the latest version of SkyShift from Github.
    git clone https://github.com/michaelzhiluo/skyshift.git

    # Install API server dependencies.
    cd skyshift
    pip install -e .[server]
