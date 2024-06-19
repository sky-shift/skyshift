.. _debug:

Debugging Tips for Contributors
-------------------------------

Installation Time Tips
++++++++++++++++++++++

- Follow :ref:`installation`. using pip's `-e/--editable` flag.

Launch Time Tips 
++++++++++++++++

- Launch the API Server and Controller Manager with --workers=1. See also :ref:`setup`.. 

.. code-block:: shell
    nohup python api_server/lauch_server.py --workers=1
    nohup python skyshift/lauch_sky_manager.py --workers=1


Runtime Tips
++++++++++++

- By default, logs are written to ~/.skyconf.
