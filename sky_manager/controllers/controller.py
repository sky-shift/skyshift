from multiprocessing import Process


class Controller(object):

    def __init__(self) -> None:
        pass

    def run(self):
        raise NotImplementedError('Subclasses must implement this method.')

    def start(self):
        self.controller_process = Process(target=self.run)
        self.controller_process.start()

    def join(self):
        self.controller_process.join()
