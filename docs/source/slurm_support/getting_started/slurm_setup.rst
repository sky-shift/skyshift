.. _slurm_setup:

Interface with a Slurm Cluster
-----------------------------------------

1. Example configuration file is provided for reference and customization:

.. code-block:: yaml

    /examples/slurm-configuration/slurmconf_example.yaml

2. Copy the example configuration file to SkyFlow configuration directory:

.. code-block:: shell

    cd /examples/slurm-configuration/slurmconf_example.yaml
    cp slurmconf_example.yaml ~/.skyconf/slurmconf.yaml


The slurmconf.yaml configuration file must be populated with specific details about your 
Slurm clusters. Below is an example of the configuration file and the fields that are required 
to be modified:

.. code-block:: yaml

    slurmcluster1:  # This is the given name of the Slurm Cluster
        slurmrestd:
            openapi_ver: vX.X.X  # Specify the OpenAPI version used by slurmrestd
            port: /var/lib/slurm/slurm.socket  # UNIX socket or URL for slurmrestd
            auth: jwt  # Authentication method for slurmrestd
        tools:
            container: containerd  # Container management tool (e.g., containerd, docker)
            runtime_dir: /home/my_runtime_dir  # Directory for container runtime
        properties:
            time_limit: 9000  # Maximum job time limit in seconds
            account: admin  # Slurm account name
        slurmcli:
            rsa_key_path: ~/rsa_key  # Path to your private RSA key
            remote_hostname: slurm.cluster.com  # Hostname of the Slurm Cluster login node
            remote_username: admin  # Username for SSH connection
        slurm_interface: cli  # Interface method (cli or rest)

    slurmcluster2:
        ...
Modifying the SkyFlow Slurm Configuration File
++++++++++++++++++++++++++++++++++++++++++++++

To integrate SkyFlow with Slurm clusters effectively, it's necessary to tailor the 
`slurmconf.yaml` configuration file to your environment. The configuration specifies 
how SkyFlow interacts with your Slurm clusters, including authentication, job management, 
and container runtime settings. Below is a structured approach to customizing your configuration file.

Configuration Syntax and Definitions
+++++++++++++++++++++++++++++++++++++

- **Option Selection `{option1|option2}`**: Some configurations require choosing between multiple options. These options are presented in curly brackets separated by a pipe (`|`). Select the appropriate option for your setup and remove the curly brackets in the actual configuration file.
  
- **Value Identification `()`**: Parameters that require a specific value from your environment are enclosed in parentheses. Replace these placeholders with the actual values relevant to your Slurm cluster setup.

Defining Clusters
+++++++++++++++++

Each Slurm cluster configuration is nested under a unique cluster name. This structure allows 
SkyFlow to manage multiple clusters simultaneously. Here is an example:

.. code-block:: yaml

    slurmcluster1:
        slurm_interface: cli

You can define as many clusters as needed by repeating the structure under different cluster names. 
Ensure the cluster name in the SkyFlow CLI command matches the one in the `slurmconf.yaml` file:

.. code-block:: shell

    skyctl create cluster slurmcluster1 --manager slurm

Key Configuration Parameters
++++++++++++++++++++++++++++

1. **slurm_interface**: Defines the method of communication with the Slurm cluster. The CLI is 
recommended.

   .. code-block:: yaml

       slurm_interface: {cli|rest}

2. **Container Manager Utility**: Selects the container management tool used by SkyFlow for job 
execution. If using ContainerD (recommended for rootless containers), set the `$XDG_RUNTIME_DIR`.

   .. code-block:: yaml

       tools:
           container: {containerd|docker|singularity}
           runtime_dir: (XDG_RUNTIME_DIR)

3. **Job and Account Settings**: Specify the maximum job time limit and the Slurm account name.

   .. code-block:: yaml

       properties:
           time_limit: (max_job_time)
           account: (your_slurm_account_name)

4. **Slurm CLI Manager**: If opting for the CLI method, configure the path to your SSH key, 
the hostname of the Slurm cluster, and your user ID on the remote cluster.

   .. code-block:: yaml

       slurmcli:
           rsa_key_path: (path_to_your_private_ssh_key)
           remote_hostname: (your_cluster_hostname)
           remote_username: (your_cluster_username)

5. **Slurm REST Manager**: For those selecting the REST interface, specify the OpenAPI version, 
the communication port, and the authentication method.

   .. code-block:: yaml

       slurmrestd:
           openapi_ver: (open_api_version)
           port: (unix_socket_or_url)
           auth: {jwt}

**Note**: Both `slurmcli` and `slurmrestd` configurations can be present simultaneously. 
The `slurm_interface` option determines the active communication method.

Required Parameters
+++++++++++++++++++

Certain parameters are critical for the proper functioning of SkyFlow with your Slurm clusters:

- **``account``**: Your Slurm account name, as authorized by your cluster's SysAdmin.
- **``rsa_key_path``**: The local path to your private SSH key for secure connections.
- **``remote_hostname``**: The network address of your Slurm cluster's login node.
- **``remote_username``**: Your username for SSH access to the Slurm cluster.

ContainerD and Rootless Container Support
++++++++++++++++++++++++++++++++++++++++++

If using a rootless container management tool such as ContainerD, follow these steps to get the runtime directory path:

1. SSH into the login node of the Slurm Cluster and run:

.. code-block:: shell

    echo $XDG_RUNTIME_DIR

.. note::

    If ``$XDG_RUNTIME_DIR`` does not return a value, manually search for the path to the rootless container manager executable.

2. Set the ``runtime_dir`` parameter in the slurmconf.yaml config file to the path obtained above.

Interfacing to a Local Slurm Cluster
++++++++++++++++++++++++++++++++++++

If SkyFlow is running on the same host machine as the Slurm Cluster controller, commands can be issued 
directly. Under the Slurm Cluster name inside the slurmconf.yaml configuration file, add the following 
property to enable direct interfacing:

.. code-block:: yaml

    slurmclustername1:
        testing:
            local: True

To switch back to remote cluster support, simply remove the ``testing`` key and its contents.

Attaching a Slurm Cluster
++++++++++++++++++++++++++++++++++++++++++

To attach a Slurm Cluster to SkyFlow, use the following command, ensuring the cluster name matches one defined in your slurmconf.yaml:

.. code-block:: shell

    skyctl create cluster slurmcluster1 --manager slurm