"""
Slurm Package.
"""
from skyshift.cluster_manager.slurm.slurm_manager_cli import SlurmManagerCLI
from skyshift.cluster_manager.slurm.slurm_manager_rest import SlurmManagerREST
from skyshift.cluster_manager.slurm.slurm_utils import (SlurmConfig,
                                                        SlurmInterfaceEnum)

__all__ = [
    'SlurmConfig', 'SlurmInterfaceEnum', 'SlurmManagerCLI', 'SlurmManagerREST'
]
