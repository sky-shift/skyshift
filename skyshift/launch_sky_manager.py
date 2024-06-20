"""
Launches the Sky Manager, which is a controller manager akin to that in K8.
"""
import traceback

from skyshift.controllers.link_controller import LinkController
from skyshift.controllers.provisioner_controller import ProvisionerController
from skyshift.controllers.skylet_controller import SkyletController
from skyshift.scheduler.scheduler_controller import SchedulerController

# Servers as the Controller Manager, which runs two controllers.
SKY_MANAGER_CONTROLLERS = [
    LinkController,
    ProvisionerController,
    SchedulerController,
    SkyletController,
]


def launch_sky_manager():
    """
    Launches the SkyShift Manager, which manages Skylets, Schedulers, and Links.
    """
    # Launch SkyletController, which manages Skylets.
    try:
        controllers = [c() for c in SKY_MANAGER_CONTROLLERS]
    except Exception:  # pylint: disable=broad-except
        print(traceback.format_exc())
        return
    for cont in controllers:
        cont.start()
    for cont in controllers:
        cont.join()


if __name__ == "__main__":
    launch_sky_manager()
