from multiprocessing import Process
import json
import traceback
import time

from sky_manager.api_server import launch_api_service

from sky_manager import utils

from sky_manager.skylet.skylet import launch_skylet
from sky_manager.controllers.scheduler_controller import SchedulerController
from sky_manager.controllers.skylet_controller import SkyletController

CONTROLLER_MANAGER_INTERVAL = 1

# Servers as the Controller Manager.
CONTROLLERS = [SkyletController, SchedulerController]


def launch_sky_manager():
    # # Launch API server with endpoint.
    # print("Launching API Server.")
    # api_server_process = Process(target=launch_api_service)
    # api_server_process.start()

    # # Give time for API server to boot up.
    # time.sleep(3)

    # Launch SkyletController, which manages Skylets.

    print("Launching Skylet Controller Manager.")
    try:
        controllers = [c() for c in CONTROLLERS]
    except Exception:
        print(traceback.format_exc())
        return
    for c in controllers:
        c.start()
    for c in controllers:
        c.join()


if __name__ == '__main__':
    launch_sky_manager()