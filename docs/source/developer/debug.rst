.. _debug:

Debugging Tips for Contributors
-------------------------------

Installation Time Tips
++++++++++++++++++++++

- Follow :ref:`installation`. using pip's `-e/--editable` flag.

Launch Time Tips 
++++++++++++++++

- For certain bugs it may be useful to launch the API Server with --workers=1. See also :ref:`setup`.. 

.. code-block:: shell
    nohup python skyflow/api_server/lauch_server.py --workers=1

- For convenience in general, the API Server and Controller Manager can be launched with a single script, launch_skyshift.sh


Runtime Tips
++++++++++++

By default, logs are written to ~/.skyconf, and each cluster's controller logs are written to subdirectories of ~/.skyconf/cluster. 
Here is an example of listing the controller logs for a cluster named "dev". 

.. code-block:: shell
    $ ls ~/.skyconf/cluster/dev/logs/
    cluster_controller.log          job_controller.log              service_controller.log
    endpoints_controller.log        network_controller.log
    flow_controller.log             proxy_controller.log