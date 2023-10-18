from multiprocessing import Process


class Controller(object):

    def __init__(self) -> None:
        pass

    def run(self):
        """
        Main control loop for the controller.
        """
        raise NotImplementedError('Subclasses must implement this method.')

    def start(self):
        """
        Start controller process.
        """
        self.controller_process = Process(target=self.run)
        self.controller_process.start()

    def join(self):
        self.controller_process.join()
