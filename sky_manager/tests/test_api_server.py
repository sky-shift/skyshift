import json
import datetime
import multiprocessing

import grpc
import pytest

from sky_manager.api_server import launch_api_service, API_SERVICE_PORT
from sky_manager.api_server.protogen import api_server_pb2_grpc, api_server_pb2

FAKE_CLUSTER_NAME = 'cluster_testing'
FAKE_JOB_NAME = 'job_testing'


@pytest.fixture(scope='class', autouse=True)
def setup_api_server():
    api_server_process = multiprocessing.Process(target=launch_api_service)
    api_server_process.start()

    channel = grpc.insecure_channel(f'localhost:{API_SERVICE_PORT}')
    stub = api_server_pb2_grpc.APIServiceStub(channel)
    yield stub

    # This code here is run after all tests finish (including failed tests).
    # Tests are run sequentially (Stateful).
    api_server_process.terminate()
    api_server_process.join()


# Tests API server with GRPC calls.
class TestAPIServerGRPC:

    def test_create_cluster(self, setup_api_server):
        stub = setup_api_server
        config = {
            'key1': '2',
            'key2': 'hello',
            'key3': str(datetime.date.today())
        }
        config_str = json.dumps(config)
        request = api_server_pb2.InputMessage(name=FAKE_CLUSTER_NAME,
                                              config=config_str)

        response = stub.CreateCluster(request)
        assert response.retcode == 0, 'Failed to create cluster, returncode is not 0.'

        response = stub.ReadCluster(request)
        json_dict = json.loads(response.config)
        assert json_dict == config, \
            f'API server received different value for cluster config, got {json_dict}'

    def test_delete_cluster(self, setup_api_server):
        stub = setup_api_server
        config = {
            'key1': '3',
        }
        config_str = json.dumps(config)
        request = api_server_pb2.InputMessage(name=FAKE_CLUSTER_NAME,
                                              config=config_str)
        stub.CreateCluster(request)
        stub.DeleteCluster(request)

        response = stub.ReadCluster(request)
        json_dict = json.loads(response.config)
        assert json_dict == None, \
            f'API server failed to delete cluster, got {json_dict}'

    def test_create_job(self, setup_api_server):
        stub = setup_api_server
        config = {
            'key1': '2',
            'key2': 'hello',
            'key3': str(datetime.date.today())
        }
        config_str = json.dumps(config)
        request = api_server_pb2.InputMessage(name=FAKE_JOB_NAME,
                                              config=config_str)

        response = stub.CreateJob(request)
        assert response.retcode == 0, 'Return code is not 0'

        response = stub.ReadJob(request)
        assert json.loads(
            response.config
        ) == config, f'Configs {response.config}, {config} do not match'

    def test_delete_job(self, setup_api_server):
        stub = setup_api_server
        config = {
            'key1': '2',
        }
        config_str = json.dumps(config)
        request = api_server_pb2.InputMessage(name=FAKE_JOB_NAME,
                                              config=config_str)
        stub.CreateJob(request)
        stub.DeleteJob(request)

        response = stub.ReadJob(request)
        json_dict = json.loads(response.config)
        assert json_dict is None, \
            f'API server failed to delete cluster, got {json_dict}'