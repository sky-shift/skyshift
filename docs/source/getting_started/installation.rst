.. _installation:

Installation
==================

.. note::

    For Macs, macOS >= 10.15 is required to install SkyShift.

To install SkyShift's python API and CLI, run:

.. code-block:: shell

    # Recommended: Create new conda env to avoid package conflicts.
    conda create -y -n SkyShift python=3.10
    conda activate SkyShift

    # Pull the latest version of SkyShift from Github.
    git clone https://github.com/michaelzhiluo/SkyShift.git

    # Install basic SkyShift dependencies.
    cd SkyShift
    pip install -e .


To install dependencies for the API server, run:

.. code-block:: shell

    # Recommended: Create new conda env to avoid package conflicts.
    conda create -y -n SkyShift python=3.10å
    conda activate SkyShift

    # Pull the latest version of SkyShift from Github.
    git clone https://github.com/michaelzhiluo/SkyShift.git

    # Install API server dependencies.
    cd SkyShift
    pip install -e .[server]
