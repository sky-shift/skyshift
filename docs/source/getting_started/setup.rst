.. _setup:

Launching SkyFlow
==================

SkyFlow depends on two components:

- API Server - Proccesses user and controller requests. Relies on FastAPI and ETCD.
- Controller Manager - Manages different controllers, which monitor and update SkyFlow state.


To launch the API server, run:

.. code-block:: shell

    # This will automatically install ETCD and launch the API server.
    cd skyflow
    nohup python api_server/lauch_server.py > /dev/null 2>&1 &

.. note::
    While we automatically install ETCD for users, it might not work for all users, so we recommend `installing ETCD manually <https://etcd.io/docs/v3.4/install/>`_.

To launch the controller manager, run:

.. code-block:: shell

    # This will automatically install ETCD and launch the API server.
    cd skyflow
    nohup python skyflow/lauch_sky_manager.py > /dev/null 2>&1 &

The controller manager will automatically detect Kubernetes clusters in ``~/.kube/config``. Alternatively, SkyFlow will identify the kubeconfig file set via the ``KUBECONFIG`` environment variable.