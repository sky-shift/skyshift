.. _slurm_setup:

Inferfacing with Slurm Clusters
================================

Skyflow interfaces with the remote Slurm Cluster through SSH, and requires the following information to connect to it:

To begin configuring the properties of the Slurm Cluster, copy the base example configuration file to the ~/.skyconf/ directory:

.. code-block:: shell

    # This will copy the example configuration file into the SkyFlow configuration directory.
    cd /examples/slurm-configuration/slurmconf_example.yaml
    /examples/slurm-configuration/slurmconf_example.yaml
    cp slurmconf_example.yaml ~/.skyconf/slurmconf.yaml

.. note::
    The example slurm configuration file **must** be modified to the specific cluster properties.

All parameters are nested underneath a Slurm Cluster name. This designation is relevent for attaching the cluster later.

.. code-block:: yaml

    slurmclustername1:
        ##property1##

        ##property2##

The following parameters inside the slurmconf.yaml configuration file are **required** to be modified.

- account - the name of the Slurm account jobs will be submitted under. This the personal account username added by the Slurm Cluster's Sysadmin.
- rsa_key_path - The file path to your private RSA key.
- remote_hostname - The hostname of the Slurm Cluster login node.
- remote_username - The username used to connect with SSH.


ContainerD and rootless container support:

If using a rootless container management tool such as ContainerD, get the runtime directory path:
1. SSH into the login node of the Slurm Cluster and run:

.. code-block:: shell

    echo $XDG_RUNTIME_DIR

.. note::
    If $XDG_RUNTIME_DIR does not return a value, the path to the rootless container manager executable will have to be manually searched for.

2. Set the runtime_dir parameter in the slurmconf.yaml config file.
- runtime_dir - the path to the runtime directory containing the rootless container executable. This is typically set by the OS environemental variable $XDG_RUNTIME_DIR.

Interfacing to a local Slurm Cluster
+++++++++++++++++++++++++++++++++++++
If SkyFlow is running on the same host machine as the Slurm Cluster controller, commands can be issued directly.

Under the Slurm Cluster name of inside the slurmconf.yaml configuration file. Add the following property to interface directly.

.. code-block:: yaml

    testing:
        local: True

The result should look like this:

.. code-block:: yaml

    slurmclustername1:
        testing:
            local: True

To return to remote cluster support, remove the testing key and everything indentended under it.
