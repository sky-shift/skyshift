"""
Slurm Package.
"""
from skyflow.cluster_manager.slurm.slurm_manager_cli import SlurmManagerCLI
from skyflow.cluster_manager.slurm.slurm_manager_rest import SlurmManagerREST
from skyflow.cluster_manager.slurm.slurm_utils import (SlurmConfig,
                                                       SlurmInterfaceEnum)

__all__ = [
    'SlurmConfig', 'SlurmInterfaceEnum', 'SlurmManagerCLI', 'SlurmManagerREST'
]
