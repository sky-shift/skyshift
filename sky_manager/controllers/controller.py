from contextlib import contextmanager
import threading
import time

CONTROLLER_RATE_LIMIT = 1

@contextmanager
def ControllerErrorHandler(controller: 'Controller'):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except Exception as e:
        pass


class Controller(object):
    """
    Represents a generic controller.

    A controller is a process that runs in the background and attempts to reconcile
    state to a desired state. This happens in the self.run() method.
    """
    def __init__(self) -> None:
        self.post_init_hook()

    def post_init_hook(self):
        """Hook that is called after the controller is initialized.
        
        This method is usually called to initialize informers and watches.
        """
        pass

    def run(self):
        """Main control loop for the controller."""
        while True:
            with ControllerErrorHandler(self):
                self.controller_loop()

    def conroller_loop(self):
        """ Write your custom controller code here."""
        time.sleep(CONTROLLER_RATE_LIMIT)

    def start(self):
        """Start controller thread."""
        self.controller_process = threading.Thread(target=self.run)
        self.controller_process.start()

    def join(self):
        """Join controller thread to the controller manager."""
        self.controller_process.join()