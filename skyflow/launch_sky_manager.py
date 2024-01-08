import traceback


from skyflow.controllers.scheduler_controller import SchedulerController
from skyflow.controllers.skylet_controller import SkyletController
from skyflow.controllers.link_controller import LinkController


# Servers as the Controller Manager, which runs two controllers.
SKY_MANAGER_CONTROLLERS = [SkyletController, SchedulerController, LinkController]

def launch_sky_manager():
    # Launch SkyletController, which manages Skylets.
    print("Launching Skylet Controller Manager.")
    try:
        controllers = [c() for c in SKY_MANAGER_CONTROLLERS]
    except Exception:
        print(traceback.format_exc())
        return
    for c in controllers:
        c.start()
    for c in controllers:
        c.join()


if __name__ == '__main__':
    launch_sky_manager()