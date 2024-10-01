.. _slurm_setup:

Setting up SkyShift to interface with Slurmn Clusters
-----------------------------------------

1. Example configuration file is provided for reference and customization:

.. code-block:: yaml

    /examples/slurm/slurm_config.yaml

2. Copy or move the example configuration file to SkyShift configuration directory:

.. code-block:: shell

    cp /examples/slurm/slurm_config.yaml ~/.skyconf/slurm_config.yaml


The slurm_config.yaml configuration file must be populated with specific details about your 
Slurm clusters. Below is a description of the fields available.

.. code-block:: yaml

    # Example of Slurm cluster accessed through CLI.
    slurmcluster2: 
        interface: cli # Cluster access interface, currently only CLI is supported.
        access_config: # Properties to authenticate and utilize the selected interface. 
            hostname: llama.millennium.berkeley.edu # Slurm server's SSH hostname.
            user: mluo # Slurm server's SSH username.
            ssh_key: ~/berzerkeley # Local path to SSH private key.
            # password: passwordexample # In the case that private keys are not supported by the SSH server, SSH password field can be exchanged with ssh_key field.

    slurmcluster2: # Second cluster field.
        ...
Customizing the SkyShift Slurm Configuration File
++++++++++++++++++++++++++++++++++++++++++++++

To integrate SkyShift with existing Slurm clusters effectively, it's necessary to tailor the 
`slurm_config.yaml` configuration file to your environment. The configuration specifies 
how SkyShift interacts with your Slurm clusters. Below is a structured approach to customizing your configuration file.

Configuration Syntax and Definitions
+++++++++++++++++++++++++++++++++++++

- **Option Selection `{option1|option2}`**: Some configurations require choosing between multiple options. These options are presented in curly brackets separated by a pipe (`|`). Select the appropriate option for your setup and remove the curly brackets in the actual configuration file.
  
- **Value Identification `()`**: Parameters that require a specific value from your environment are enclosed in parentheses. Replace these placeholders with the actual values relevant to your Slurm cluster environment.

Defining Clusters
+++++++++++++++++

Each Slurm cluster configuration is nested under a unique cluster name. This structure allows 
SkyShift to manage multiple clusters simultaneously. Here is an example:
You can define as many clusters as needed by repeating the structure under unique cluster names. 

.. code-block:: yaml

    slurmcluster1: # Cluster name identifier
        interface: cli
        access_config:
            ...
    slurmcluster2:
        ...

Key Configuration Parameters
++++++++++++++++++++++++++++

1. **interface**: Defines the method of communication with the Slurm cluster. The CLI is 
recommended.

   .. code-block:: yaml

       interface: {cli|rest}

2. **Slurm CLI Interface**: If opting for the CLI method, configure the path to your SSH key, 
the hostname of the Slurm cluster, and your user ID on the remote cluster. The preferred method is RSA key authentiation, but the ssh_key field can be exchanged for password for password authentiation.  

   .. code-block:: yaml
        
    access_config:
        hostname: llama.millennium.berkeley.edu
        user: mluo
        ssh_key: ~/berzerkeley
        # password: whatever

4. **Slurm REST Interface**: `CURRENTLY UNSUPPORTED` For those selecting the REST interface, specify the OpenAPI version, 
the communication port, and the authentication method. This is currently unsupported as most Slurm cluster's have yet to adopt this interface.

   .. code-block:: yaml

       access_config:
            openapi_ver: v0.0.38 # Version of OpenAPI used by slurmrestd.
            port: /var/lib/slurm/slurmrestd.socket # Port used to communicate with the server.
            auth: jwt # Authentication method used by the REST endpoint.

5. Attaching a Slurm Cluster
++++++++++++++++++++++++++++++++++++++++++

If launching SkyShift, SkyShift will automatically read the slurm_config.yaml file and try to attach the Slurm clusters.

To launch SkyShift, run in `skyshift/`:

.. code-block:: shell

    ./launch_skyshift.sh


If SkyShift is already running and the cluster has not been added yet, attach the cluster.

.. code-block:: shell

    skyctl create cluster slurmcluster1 --manager slurm