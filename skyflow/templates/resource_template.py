"""
Resource template for Skyflow.
"""
import enum


class CRIEnum(enum.Enum):
    """Enum for upported container runtime interfaces (CRI)."""
    CONTAINERD = "containerd"
    SINGULARITY = "singularity"
    PODMAN = "podman"
    PODMANHPC = "podman-hpc"
    DOCKER = "docker"
    NONE = "none"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class ResourceEnum(enum.Enum):
    """Different types of compute resources."""
    # CPUs
    CPU: str = "cpus"
    # Generic GPUs
    GPU: str = "gpus"
    # Memory is expressed in MB.
    MEMORY: str = "memory"
    # Disk is also expressed in MB.
    DISK: str = 'disk'


class AcceleratorEnum(enum.Enum):
    """
    Different types of accelerators (GPUs) from NVIDIA.
    """
    # A Series
    A100: str = "A100"
    A30: str = "A30"
    A40: str = "A40"
    A10: str = "A10"
    A16: str = "A16"
    A2: str = "A2"

    # H Series
    H100: str = "H100"
    H800: str = "H800"

    # T Series
    T4: str = "T4"
    T10: str = "T10"

    # V Series
    V100: str = "V100"
    V100S: str = "V100S"

    # P Series
    P100: str = "P100"
    P40: str = "P40"
    P4: str = "P4"
    P20: str = "P20"
    P6: str = "P6"

    # K Series
    K80: str = "K80"
    K40: str = "K40"
    K20: str = "K20"
    K10: str = "K10"
    K5200: str = "K5200"

    # M Series
    M60: str = "M60"
    M40: str = "M40"
    M30: str = "M30"
    M10: str = "M10"
    M6: str = "M6"
    M4: str = "M4"

    # GeForce 10 Series
    GTX_1080: str = "GTX 1080"
    GTX_1080_TI: str = "GTX 1080 Ti"
    GTX_1070: str = "GTX 1070"
    GTX_1070_TI: str = "GTX 1070 Ti"
    GTX_1060: str = "GTX 1060"
    GTX_1050: str = "GTX 1050"
    GTX_1050_TI: str = "GTX 1050 Ti"
    GT_1030: str = "GT 1030"
    GT_1010: str = "GT 1010"

    # GeForce 16 Series
    GTX_1660: str = "GTX 1660"
    GTX_1660_TI: str = "GTX 1660 Ti"
    GTX_1650: str = "GTX 1650"
    GTX_1650_SUPER: str = "GTX 1650 Super"

    # GeForce 20 Series
    RTX_2080: str = "RTX 2080"
    RTX_2080_TI: str = "RTX 2080 Ti"
    RTX_2070: str = "RTX 2070"
    RTX_2070_SUPER: str = "RTX 2070 Super"
    RTX_2060: str = "RTX 2060"
    RTX_2060_SUPER: str = "RTX 2060 Super"

    # GeForce 30 Series
    RTX_3090: str = "RTX 3090"
    RTX_3080: str = "RTX 3080"
    RTX_3080_TI: str = "RTX 3080 Ti"
    RTX_3070: str = "RTX 3070"
    RTX_3070_TI: str = "RTX 3070 Ti"
    RTX_3060: str = "RTX 3060"
    RTX_3060_TI: str = "RTX 3060 Ti"

    # GeForce 40 Series
    RTX_4090: str = "RTX 4090"
    RTX_4080: str = "RTX 4080"
    RTX_4070: str = "RTX 4070"
    RTX_4060: str = "RTX 4060"
    RTX_4050: str = "RTX 4050"

    # Quadro Series
    QUADRO_RTX_8000: str = "Quadro RTX 8000"
    QUADRO_RTX_6000: str = "Quadro RTX 6000"
    QUADRO_RTX_5000: str = "Quadro RTX 5000"
    QUADRO_P5000: str = "Quadro P5000"
    QUADRO_P4000: str = "Quadro P4000"
    QUADRO_P2200: str = "Quadro P2200"
    QUADRO_M5000: str = "Quadro M5000"
    QUADRO_M4000: str = "Quadro M4000"
    QUADRO_K6000: str = "Quadro K6000"
    QUADRO_K5200: str = "Quadro K5200"
    QUADRO_K4200: str = "Quadro K4200"

    # Tesla Series
    TESLA_K80: str = "Tesla K80"
    TESLA_K40: str = "Tesla K40"
    TESLA_K20: str = "Tesla K20"
    TESLA_M60: str = "Tesla M60"
    TESLA_M40: str = "Tesla M40"
    TESLA_M30: str = "Tesla M30"
    TESLA_P100: str = "Tesla P100"
    TESLA_P40: str = "Tesla P40"
    TESLA_P4: str = "Tesla P4"
    TESLA_V100: str = "Tesla V100"

    # Jetson Series
    JETSON_TX2: str = "Jetson TX2"
    JETSON_XAVIER_NX: str = "Jetson Xavier NX"
    JETSON_NANO: str = "Jetson Nano"
    JETSON_AGX_ORIN: str = "Jetson AGX Orin"

    # Titan Series
    TITAN_RTX: str = "Titan RTX"
    TITAN_V: str = "Titan V"
    TITAN_X: str = "Titan X"
    TITAN_XP: str = "Titan Xp"

    # RTX A Series (Professional GPUs)
    RTX_A6000: str = "RTX A6000"
    RTX_A5000: str = "RTX A5000"
    RTX_A4000: str = "RTX A4000"
    RTX_A2000: str = "RTX A2000"

    # Other models
    GRID_K520: str = "GRID K520"
    GRID_M40: str = "GRID M40"
    GRID_DGX_A100: str = "GRID DGX A100"
    NVIDIA_DGX_1: str = "NVIDIA DGX-1"
    NVIDIA_DGX_2: str = "NVIDIA DGX-2"
    NVIDIA_DGX_STATION: str = "NVIDIA DGX Station"

    # Failed GPUs
    NOGPU: str = "NoGPU"
    UNKGPU: str = "UnknownGPU"
