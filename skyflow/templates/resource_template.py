"""
Resource template for Skyflow.
"""
import enum

class ContainerEnum(enum.Enum):
    """Selector for supported container managers"""
    CONTAINERD = "CONTAINERD"
    SINGULARITY = "SINGULARITY"
    PODMAN = "PODMAN"
    PODMANHPC = "PODMANHPC"
    DOCKER = "DOCKER"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

class ResourceEnum(enum.Enum):
    """
    Different types of resources.
    """
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
    GTX1080: str = "GTX 1080"
    GTX1080Ti: str = "GTX 1080 Ti"
    GTX1070: str = "GTX 1070"
    GTX1070Ti: str = "GTX 1070 Ti"
    GTX1060: str = "GTX 1060"
    GTX1050: str = "GTX 1050"
    GTX1050Ti: str = "GTX 1050 Ti"
    GT1030: str = "GT 1030"
    GT1010: str = "GT 1010"

    # GeForce 16 Series
    GTX1660: str = "GTX 1660"
    GTX1660Ti: str = "GTX 1660 Ti"
    GTX1650: str = "GTX 1650"
    GTX1650Super: str = "GTX 1650 Super"

    # GeForce 20 Series
    RTX2080: str = "RTX 2080"
    RTX2080Ti: str = "RTX 2080 Ti"
    RTX2070: str = "RTX 2070"
    RTX2070Super: str = "RTX 2070 Super"
    RTX2060: str = "RTX 2060"
    RTX2060Super: str = "RTX 2060 Super"

    # GeForce 30 Series
    RTX3090: str = "RTX 3090"
    RTX3080: str = "RTX 3080"
    RTX3080Ti: str = "RTX 3080 Ti"
    RTX3070: str = "RTX 3070"
    RTX3070Ti: str = "RTX 3070 Ti"
    RTX3060: str = "RTX 3060"
    RTX3060Ti: str = "RTX 3060 Ti"

    # GeForce 40 Series
    RTX4090: str = "RTX 4090"
    RTX4080: str = "RTX 4080"
    RTX4070: str = "RTX 4070"
    RTX4060: str = "RTX 4060"
    RTX4050: str = "RTX 4050"

    # Quadro Series
    QuadroRTX8000: str = "Quadro RTX 8000"
    QuadroRTX6000: str = "Quadro RTX 6000"
    QuadroRTX5000: str = "Quadro RTX 5000"
    QuadroP5000: str = "Quadro P5000"
    QuadroP4000: str = "Quadro P4000"
    QuadroP2200: str = "Quadro P2200"
    QuadroM5000: str = "Quadro M5000"
    QuadroM4000: str = "Quadro M4000"
    QuadroK6000: str = "Quadro K6000"
    QuadroK5200: str = "Quadro K5200"
    QuadroK4200: str = "Quadro K4200"

    # Tesla Series
    TeslaK80: str = "Tesla K80"
    TeslaK40: str = "Tesla K40"
    TeslaK20: str = "Tesla K20"
    TeslaM60: str = "Tesla M60"
    TeslaM40: str = "Tesla M40"
    TeslaM30: str = "Tesla M30"
    TeslaP100: str = "Tesla P100"
    TeslaP40: str = "Tesla P40"
    TeslaP4: str = "Tesla P4"
    TeslaV100: str = "Tesla V100"

    # Jetson Series
    JetsonTX2: str = "Jetson TX2"
    JetsonXavierNX: str = "Jetson Xavier NX"
    JetsonNano: str = "Jetson Nano"
    JetsonAGXOrin: str = "Jetson AGX Orin"

    # Titan Series
    TitanRTX: str = "Titan RTX"
    TitanV: str = "Titan V"
    TitanX: str = "Titan X"
    TitanXp: str = "Titan Xp"

    # RTX A Series (Professional GPUs)
    RTXA6000: str = "RTX A6000"
    RTXA5000: str = "RTX A5000"
    RTXA4000: str = "RTX A4000"
    RTXA2000: str = "RTX A2000"

    # Other models
    GRIDK520: str = "GRID K520"
    GRIDM40: str = "GRID M40"
    GRIDDGXA100: str = "GRID DGX A100"
    NVIDIADGX1: str = "NVIDIA DGX-1"
    NVIDIADGX2: str = "NVIDIA DGX-2"
    NVIDIADGXStation: str = "NVIDIA DGX Station"

