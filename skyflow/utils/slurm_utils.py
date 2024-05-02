import paramiko 
import os
import yaml
import logging
import enum
from skyflow.globals import SLURM_CONFIG_PATH
from skyflow.globals import SLURM_SUPPORTED_INTERFACES
from skyflow.globals import SKYCONF_DIR
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")
class ConfigNotDefinedError(Exception):
    """ Raised when there is an error in slurm config yaml. """
    def __init__(self, variable_name):
        self.variable_name = variable_name
        super().__init__(f"Variable '{variable_name}' is not provided in the YAML file.")
class SlurmctldConnectionError(Exception):
    """ Raised when there is an error connecting to slurmctld. """
class SSHConnectionError(Exception):
    """ Raised when there is an error establishing SSH connection to slurm cluster. """
class SlurmInterfaceEnum(enum.Enum):
    REST = 'rest'
    CLI = 'cli'
SLURM_LOG_DIR = SKYCONF_DIR + '/slurm/'
SLURM_JOB_LOG = SLURM_LOG_DIR + 'skyflow_slurm_logs.log'
def log_job(msg):
    if not os.path.exists(SLURM_LOG_DIR):
        logging.info(f"Creating directory '{SLURM_LOG_DIR}'")
        os.makedirs(Path(SLURM_LOG_DIR))
    if not os.path.exists(SLURM_JOB_LOG):
        try:
            logging.info(f"Creating log file '{SLURM_JOB_LOG}'")
            with open(SLURM_JOB_LOG, 'w'):  
                pass  
        except OSError as e:
            logging.info(f"Error creating file '{SLURM_JOB_LOG}'")
    try:
        with open(SLURM_JOB_LOG, 'a') as file:
            file.write(msg + '\n')  # Append content to the file
    except OSError as e:
        logging.info(f"Error appending to file '{SLURM_JOB_LOG}'")
def get_config(config_dict, key, optional=False) -> str:
    """Fetches key from config dict extracted from yaml.
        Allows optional keys to be fetched without returning an error.

        Args: 
            config_dict: dictionary of nested key value pairs.
            key: array of keys, forming the nested key path.
            optional: whether the key in the yaml is optional or not.
        Returns:
            key: the value associated with the key path
    """
        
    config_val = config_dict
    nested_path = ''
    if not optional:
        for i in range(len(key)):
            nested_path += key[i]
            if key[i] not in config_val:
                raise ConfigNotDefinedError(nested_path)
                return ''
            else:
                config_val = config_val[key[i]]
    else:
        for i in range(len(key)):
            nested_path += key[i]
            if key[i] not in config_val:
                return ''
            else:
                config_val = config_val[key[i]]
    return config_val
def check_reachable(remote_hostname, remote_username, rsa_key='', passkey='', uses_passkey = False):
        """ Sanity check to make sure login node is reachable via SSH.
        """
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
        # Connect to the SSH server
            if uses_passkey:
                ssh_client.connect(hostname = remote_hostname,
                    username = remote_username, password=passkey)
                logging.info('Slurm Cluster: ' + remote_hostname + '@' + remote_username + ' Reachable')

            else:
                ssh_client.connect(hostname = remote_hostname,
                    username = remote_username, pkey = rsa_key)
                logging.info('Slurm Cluster: ' + remote_hostname + '@' + remote_username + ' Reachable')

        except paramiko.AuthenticationException:
            logging.info('Unable to authenticate user, please check configuration')
            return False
        except paramiko.SSHException:
            logging.info('SSH protocol negotiation failed, \
            please check if remote server is reachable') 
            return False
        except Exception:
            logging.info("Unexpected exception") 
            return False
        #ssh_client.close()
        return True
def check_key_existence(config_dict, key):
    """Checks if key exists in the yaml.

        Args: 
            config_dict: dictionary of nested key value pairs.
            key: array of keys, forming the nested key path.
            optional: whether the key in the yaml is optional or not.
        Returns:
            True or false if the key exists or not.
    """
    config_val = config_dict
    for i in range(len(key)):
        if key[i] not in config_val:
            return False
        else:
            config_val = config_val[key[i]]
    return True
class VerifySlurmConfig():
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)
        config_absolute_path = os.path.expanduser(SLURM_CONFIG_PATH)
        with open(config_absolute_path, 'r') as config_file:
            self.config_dict = yaml.safe_load(config_file)
        self.interface_type = SlurmInterfaceEnum.CLI
    def verify_all_clusters(self):
        for cluster_name in self.config_dict:
            self.verify_configuration(str(cluster_name))
    def get_clusters(self):
        return self.config_dict.keys()
    def verify_configuration(self, cluster_name):
        if not check_key_existence(self.config_dict, [cluster_name]):
            self.logger.info('Cluster name provided does not match one in the yaml.')
            return False
        cluster_dict = self.config_dict[cluster_name]

        interface_key = ['slurm_interface']
        if not check_key_existence(cluster_dict, interface_key):
            self.log_slurm('Interface key not present in yaml', 'slurm_interface', cluster_name)
            return False
        interface = get_config(cluster_dict, interface_key)
        if interface not in SLURM_SUPPORTED_INTERFACES:
            self.log_slurm('Unsupported Slurm interface requested', 'slurm_interface', cluster_name)
            return False
        else: 
            if 'rest' in interface.lower():
                if self.verify_rest_config(cluster_dict):
                    self.logger.info('Slurm REST endpoint reachable!')
                    self.interface_type = SlurmInterfaceEnum.REST
                    return True
            else:
                if self.verify_cli_config(cluster_dict):
                    self.logger.info('Slurm CLI login node reachable!')
                    return True
        return False
    def log_slurm(self, message, cluster_name, bad_key):
        log_msg = message + ' Check ' + bad_key + ' in ' + cluster_name + ' in configuration at ' + SLURM_CONFIG_PATH
        self.logger.info(log_msg)

    def verify_cli_config(self, cluster_dict):
        remote_hostname = get_config(cluster_dict, ['slurmcli', 'remote_hostname'])
        remote_username = get_config(cluster_dict, ['slurmcli', 'remote_username'])
        if not check_key_existence(cluster_dict, ['testing', 'passkey']):
            rsa_key_path = get_config(cluster_dict, ['slurmcli','rsa_key_path'])
            rsa_key_path = os.path.expanduser(rsa_key_path)
            if not os.path.exists(rsa_key_path):
                raise ValueError(
                f'RSA private key file does not exist! {rsa_key_path} in \
                {SLURM_CONFIG_PATH}.')
            
            rsa_key = paramiko.RSAKey.from_private_key_file(rsa_key_path)
            return check_reachable(remote_hostname, remote_username, rsa_key=rsa_key)
        else:
            passkey = get_config(cluster_dict, ['testing', 'passkey'])
            return check_reachable(remote_hostname, remote_username, passkey=passkey, uses_passkey=True)
    def verify_rest_config(self, nested_dict):
        raise NotImplementedError
if __name__ == '__main__':
    config_absolute_path = os.path.expanduser(SLURM_CONFIG_PATH)

    with open(config_absolute_path, 'r') as config_file:
        config_dict = yaml.safe_load(config_file)
        vf = VerifySlurmConfig()
        vf.verify_all_clusters()