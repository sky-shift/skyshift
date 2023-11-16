from sky_manager.utils.utils import load_manager_config
from sky_manager.utils import load_object
def verify_response(response):
    if 'detail' in response:
        raise Exception(response['detail'])
    return load_object(response)


class ObjectAPI(object):

    def __init__(self):
        self.host, self.port = load_manager_config()

    def create(self, config: dict):
        raise NotImplementedError('Create is not implemented')

    def update(self, config: dict):
        raise NotImplementedError('Update is not implemented')

    def list(self):
        raise NotImplementedError('List is not implemented')

    def get(self, name: str):
        raise NotImplementedError('Get is not implemented')

    def delete(self, name: str):
        raise NotImplementedError('Delete is not implemented')

    def watch(self):
        raise NotImplementedError('Watch is not implemented')