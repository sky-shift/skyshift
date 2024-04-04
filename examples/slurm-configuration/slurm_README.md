# Initial README for Slurm

### 1. Creating SkyFlow Slurm configuration file.
    Example configuration file.
    ```
    /examples/slurm-configuration/slurmconf_example.yaml
    ```
    Copy configuration file to SkyFlow configuration directory. 
    ```
    cp slurmconf_example.yaml ~/.skyconf/slurmconf.yaml
    ```

### 2. Modifying SkyFlow Slurm configuration file
    The following fields must be populated.
    
    Syntax {option1|option2} symbolizes to pick one of options seperated by '|' provided in the curly brackets, while omitting the curly brackets in the configuration file.

    Syntax () symbolizes a value you must identify.

    Define each cluster.
    All parameters needed are nested under a cluster name. Eg.
    ```
    slurmtestcluster1:
        slurm_interface: cli
    ```
    Infinite cluster names can be added, and when attaching such cluster from skyflow CLI, the cluster name must match this one in order to fetch the parameters correctly. Eg.
    ```
        skyctl create cluster slurmtestcluster1 --manager slurm 
    ```

    slurm_interface: Select the manager type. Communication to cluster through REST API endpoints, or interfacing through CLI. CLI manager is recommended.
    ```
        slurm_interface: {cli|rest}
    ```
    Select the container manager utility
    
    Set the $XDG_RUNTIME_DIR (typically set by the OS of the cluster), where rootless container binaries are located. This is only required for ContainerD as of now.
    ```
        tools:
            container: {containerd|docker|singularity} 
            runtime_dir: (XDG_RUNTIME_DIR)
    ```
    Set the max job time limit and Slurm user account name.
    ```
        properties: 
            time_limit: (max_job_time)
            account: (my_slurm_username)
    ```
    If selecting Slurm CLI manager set slurmcli property.
    ```
        slurmcli: 
            rsa_key_path: (path_to_private_ssh_key)
            remote_hostname: (full_hostname_of_remote_cluster)
            remote_username: (user_id_on_remote_cluster)
    ```
    If selecting Slurm REST manager set the slurmrestd property.
    ```
        slurmrestd:
            openapi_ver: (open_api_version)
            port: (unix_socket_or_url)
            auth: {jwt}
    ```
    **Note, both of these properties can be presesnt in config at once. slurm_interface property is utilized as the selector.

### 3. Attaching Slurm Cluster
    Attach Slurm Cluster to Skyflow.
    ```
        skyctl create cluster slurmt5 --manager slurm 
    ```
### 4. Running a job
    ```
        skyctl create job --cpus 1 --image ubuntu --memory 32 --run "echo hi;sleep 5000" test_job1
    ```
