"""
Launches the Sky Manager, which is a controller manager akin to that in K8.
"""
import traceback

from skyflow.controllers.link_controller import LinkController
from skyflow.controllers.scheduler_controller import SchedulerController
from skyflow.controllers.skylet_controller import SkyletController

# Servers as the Controller Manager, which runs two controllers.
SKY_MANAGER_CONTROLLERS = [
    SkyletController, SchedulerController, LinkController
]


def launch_sky_manager():
    """
    Launches the Sky Manager, which manages Skylets, Schedulers, and Links.
    """
    # Launch SkyletController, which manages Skylets.
    print("Launching Skylet Controller Manager.")
    try:
        controllers = [c() for c in SKY_MANAGER_CONTROLLERS]
    except Exception: # pylint: disable=broad-except
        print(traceback.format_exc())
        return
    for cont in controllers:
        cont.start()
    for cont in controllers:
        cont.join()


if __name__ == "__main__":
    launch_sky_manager()
