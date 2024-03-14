.. _installation:

Installation
==================

.. note::

    For Macs, macOS >= 10.15 is required to install SkyFlow.

To install Skyflow, run:

.. tabs::

    .. tab:: Users
        .. code-block:: shell
          # Users are assumed to have pre-existing access to a SkyFlow instance.
          # Users interface SkyFlow through an existing SkyFlow Config.
          # Recommended: Create new conda env to avoid package conflicts.
          conda create -y -n skyflow python=3.10
          conda activate skyflow

          # Install SkyFlow dependencies.
          pip install -e .


    .. tab:: Admins
        .. code-block:: shell
          # Recommended: Create new conda env to avoid package conflicts.
          conda create -y -n skyflow python=3.10
          conda activate skyflow

          # Choose your cloud:
          pip install -e .
          pip install -e .[server]