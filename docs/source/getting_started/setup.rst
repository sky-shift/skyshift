.. _setup:

Launching SkyShift
==================

SkyShift depends on two components:

- API Server - Proccesses user and controller requests. Relies on FastAPI and ETCD.
- Controller Manager - Manages different controllers, which monitor and update SkyShift state.

More information can be found under SkyShift's architecture.

To launch the API server, run:

.. code-block:: shell

    # This will automatically install ETCD and launch the API server.
    cd skyshift
    nohup python api_server/lauch_server.py > /dev/null 2>&1 &

.. note::
    While SkyShift automatically installs ETCD for users, it might not work for all users, so `installing ETCD manually <https://etcd.io/docs/v3.4/install/>`_ might be neccessary.

To launch the controller manager, run:

.. code-block:: shell

    # This will automatically install ETCD and launch the API server.
    cd skyshift
    nohup python skyshift/lauch_sky_manager.py > /dev/null 2>&1 &

The controller manager will automatically detect Kubernetes clusters in ``~/.kube/config``.