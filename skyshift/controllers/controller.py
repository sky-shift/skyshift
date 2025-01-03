"""
The Controller class is a generic controller that can be used to implement
custom controllers.
"""
import logging
import threading
import traceback
from contextlib import contextmanager
from typing import Optional

import requests

from skyshift.templates.cluster_template import Cluster


@contextmanager
def controller_error_handler(controller: "Controller"):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError:
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Cannot connect to API server. Retrying.")
    except Exception:  # pylint: disable=broad-except
        controller.logger.error(traceback.format_exc())


class Controller:
    """
    Represents a generic controller.

    A controller is a process that runs in the background and attempts to reconcile
    state to a desired state. This happens in the self.run() method.
    """

    def __init__(self, cluster_obj: Optional[Cluster] = None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.controller_process: threading.Thread = threading.Thread(
            target=self.run)
        self.cluster = cluster_obj

    def post_init_hook(self):  # pylint: disable=no-self-use
        """Hook that is called after the controller is initialized.

        This method is usually called to initialize informers and watches.
        """
        return

    def run(self):
        """Main control loop for the controller."""
        while True:
            with controller_error_handler(self):
                self.controller_loop()

    def controller_loop(self):
        """Write your custom controller code here."""
        raise NotImplementedError

    def start(self):
        """Start controller thread."""
        # Run post initialization hook.
        self.post_init_hook()
        self.controller_process.start()

    def join(self):
        """Join controller thread to the controller manager."""
        self.controller_process.join()
