import unittest
import json
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
import yaml
import asyncio

from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException

from api_server.api_server import APIServer, app
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.templates import Namespace, NamespaceMeta, ObjectException
from skyflow.templates.cluster_template import Cluster
from skyflow.templates.endpoints_template import Endpoints
from skyflow.templates.filter_policy import FilterPolicy
from skyflow.templates.job_template import Job, JobException
from skyflow.templates.link_template import Link
from skyflow.templates.service_template import Service, ServiceException

NAMESPACED_OBJECTS = {"jobs": Job, "filterpolicies": FilterPolicy, "services": Service, "endpoints": Endpoints}
NON_NAMESPACED_OBJECTS = {"clusters": Cluster, "namespaces": Namespace, "links": Link}
ALL_OBJECTS = {**NAMESPACED_OBJECTS, **NON_NAMESPACED_OBJECTS}

class TestAPIServer(unittest.TestCase):
    @patch('api_server.api_server.ETCDClient')
    def setUp(self, mock_etcd_client):
        """
        Set up the test environment by mocking the ETCDClient and 
        initializing the APIServer.
        """
        self.mock_etcd_client_instance = mock_etcd_client.return_value
        with patch.object(APIServer, '_post_init_hook', return_value=None):
            self.api_server = APIServer()
            
    def run_async(self, coro):
        """
        Utility method to run the coroutine and manage the event loop.
        """
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_post_init_hook_with_default_namespace(self):
        """
        Test the post initialization hook when the default namespace already exists.
        """
        self.mock_etcd_client_instance.read_prefix.return_value = [DEFAULT_NAMESPACE]
        self.api_server._post_init_hook()
        self.mock_etcd_client_instance.write.assert_not_called()

    def test_post_init_hook_without_default_namespace(self):
        """
        Test the post initialization hook when the default namespace does not exist.
        """
        self.mock_etcd_client_instance.read_prefix.return_value = []
        self.api_server._post_init_hook()
        expected_namespace = Namespace(metadata=NamespaceMeta(name=DEFAULT_NAMESPACE)).model_dump(mode="json")
        self.mock_etcd_client_instance.write.assert_called_with(
            "namespaces/default",
            expected_namespace
        )
    
    def test_create_object_with_different_headers(self):
        """
        Test the creation of objects with different content types in request headers.
        """
        async def async_test():
            # Test scenarios
            scenarios = [
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "json_test_object"}}), "expected_success": True},
                {"content_type": "application/yaml", "body": yaml.dump({"metadata": {"name": "yaml_test_object"}}), "expected_success": True},
                {"content_type": "text/plain", "body": "plain text", "expected_success": False},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("jobs")

                    if scenario["expected_success"]:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()
                    else:
                        with self.assertRaises(HTTPException):
                            await self.create_object(mock_request)

        
        self.run_async(async_test())

    def test_job_creation_with_different_specs(self):
        """
        Test the creation of Job objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with invalid specs
            scenarios = [
                # Metadata name tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # Replicas tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"replicas": 0}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"replicas": -1}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"replicas": "invalid"}}), "expected_exception": ValidationError},

                # Resource tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"resources": {"CPU": -1}}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"resources": {"MEMORY": -100}}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"resources": {"GPU": -2}}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"resources": {"GPU": "two"}}}), "expected_exception": ValidationError},

                # Image tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"image": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"image": 123}}), "expected_exception": ValidationError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"image": "ubuntu:latest"}}), "expected_exception": None},  # Valid case
                {"content_type": "application/json", "body": json.dumps({"spec": {"image": "alex/personal/repo/path/cool-image:latest"}}), "expected_exception": None},  # Valid case

                # Environment variables tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"envs": {"VAR1": None}}}), "expected_exception": ValidationError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"envs": {"VAR1": 123}}}), "expected_exception": ValidationError},

                # Ports tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"ports": [-1]}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"ports": [0]}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"ports": [70000]}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"ports": ["invalid"]}}), "expected_exception": ValidationError},

                # Restart policy tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"restart_policy": "InvalidPolicy"}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"spec": {"restart_policy": ""}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"spec": {"restart_policy": 123}}), "expected_exception": ValidationError},

                # Run command tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"run": ""}}), "expected_exception": None},  # Valid case
                {"content_type": "application/json", "body": json.dumps({"spec": {"run": 123}}), "expected_exception": ValidationError},

                # Full spec with invalid combination tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"image": "ubuntu:latest", "replicas": -1, "resources": {"CPU": "two"}}}), "expected_exception": ValueError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("jobs")

                    
                    print(scenario["body"])
                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                         await self.create_object(mock_request)
                         self.mock_etcd_client_instance.write.assert_called()

        
        self.run_async(async_test())

    def test_filter_policy_creation_with_various_specs(self):
        """
        Test the creation of FilterPolicy objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with various specs for FilterPolicy
            scenarios = [
                # Valid FilterPolicy
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "validPolicy"}, "spec": {"cluster_filter": {"include": ["clusterA"], "exclude": ["clusterB"]}}}), "expected_exception": None},

                # Metadata tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # ClusterFilter tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"cluster_filter": {"include": -1}}}), "expected_exception": ValidationError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"cluster_filter": {"exclude": {"clusterC": "value"}}}}), "expected_exception": ValidationError},

                # Labels selector tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"labels_selector": {"key": 123}}}), "expected_exception": ValidationError},

                # Status tests
                {"content_type": "application/json", "body": json.dumps({"status": {"status": "INVALID_STATUS"}}), "expected_exception": ValueError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("filterpolicies")

                    if scenario["expected_exception"]:
                        
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                        
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()

        
        self.run_async(async_test())

    def test_service_creation_with_various_specs(self):
        """
        Test the creation of Service objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with various specs for Service
            scenarios = [
                # Valid Service
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "validService"}, "spec": {"type": "ClusterIP", "ports": [{"port": 80, "target_port": 80}]}}), "expected_exception": None},

                # Metadata tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # Service type tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"type": "InvalidType"}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"spec": {"type": None}}), "expected_exception": ValidationError},

                # Ports tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"ports": [{"port": -1, "target_port": 80}]}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"spec": {"ports": [{"port": 80, "target_port": "invalid"}]}}), "expected_exception": ValidationError},

                # Cluster IP tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"cluster_ip": -1}}), "expected_exception": ValidationError},

                # Primary Cluster tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"primary_cluster": -1}}), "expected_exception": ValidationError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("services")

                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()

        
        self.run_async(async_test())

    def test_endpoints_creation_with_various_specs(self):
        """
        Test the creation of Endpoints objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with various specs for Endpoints
            scenarios = [
                # Valid Endpoints
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "validEndpoints"}, "spec": {"selector": {"key": "value"}, "endpoints": {"clusterA": {"num_endpoints": 2, "exposed_to_cluster": True}}}}), "expected_exception": None},

                # Metadata tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # Selector tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"selector": {"key": 123}}}), "expected_exception": ValidationError},

                # Endpoints tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"endpoints": {"clusterA": {"num_endpoints": -1}}}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"spec": {"endpoints": {"clusterA": {"exposed_to_cluster": "invalid"}}}}), "expected_exception": ValidationError},

                # Primary cluster tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"primary_cluster": -1}}), "expected_exception": ValidationError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("endpoints")

                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()

        
        self.run_async(async_test())

    def test_cluster_creation_with_various_specs(self):
        """
        Test the creation of Cluster objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with various specs for Cluster
            scenarios = [
                # Valid Cluster
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "validCluster"}, "spec": {"manager": "k8"}, "status": {"status": "READY"}}), "expected_exception": None},

                # Metadata tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # Manager field tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"manager": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"spec": {"manager": 123}}), "expected_exception": ValidationError},

                # Status field tests
                {"content_type": "application/json", "body": json.dumps({"status": {"status": "INVALID_STATUS"}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"status": {"status": None}}), "expected_exception": ValidationError},

                # Capacity field tests
                {"content_type": "application/json", "body": json.dumps({"status": {"capacity": {"nodeA": {"CPU": -1}}}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"status": {"capacity": {"nodeA": {"GPU": "invalid"}}}}), "expected_exception": ValidationError},

                # Allocatable Capacity tests
                {"content_type": "application/json", "body": json.dumps({"status": {"allocatable_capacity": {"nodeA": {"MEMORY": -100}}}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"status": {"allocatable_capacity": {"nodeA": {"ACCELERATOR": "invalid"}}}}), "expected_exception": ValidationError},

                # Accelerator Types tests
                {"content_type": "application/json", "body": json.dumps({"status": {"accelerator_types": {"nodeA": -1}}}), "expected_exception": ValidationError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("clusters")

                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()

        
        self.run_async(async_test())

    def test_namespace_creation_with_various_specs(self):
        """
        Test the creation of Namespace objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with various specs for Namespace
            scenarios = [
                # Valid Namespace
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "validNamespace"}, "status": {"status": "ACTIVE"}}), "expected_exception": None},

                # Metadata tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # Status field tests
                {"content_type": "application/json", "body": json.dumps({"status": {"status": "INVALID_STATUS"}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"status": {"status": None}}), "expected_exception": ValidationError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("namespaces")

                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()

        
        self.run_async(async_test())

    def test_link_creation_with_various_specs(self):
        """
        Test the creation of Link objects with various specifications, including invalid specs.
        """
        async def async_test():
            # Define scenarios with various specs for Link
            scenarios = [
                # Valid Link
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": "validLink"}, "spec": {"source_cluster": "clusterA", "target_cluster": "clusterB"}, "status": {"phase": "ACTIVE"}}), "expected_exception": None},

                # Metadata tests
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": ""}}), "expected_exception": ValueError},
                {"content_type": "application/json", "body": json.dumps({"metadata": {"name": 123}}), "expected_exception": ValidationError},

                # Source and Target Cluster tests
                {"content_type": "application/json", "body": json.dumps({"spec": {"source_cluster": "", "target_cluster": "clusterB"}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"spec": {"source_cluster": "clusterA", "target_cluster": ""}}), "expected_exception": HTTPException},

                # Phase status tests
                {"content_type": "application/json", "body": json.dumps({"status": {"phase": "INVALID_PHASE"}}), "expected_exception": HTTPException},
                {"content_type": "application/json", "body": json.dumps({"status": {"phase": None}}), "expected_exception": ValidationError},
            ]

            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": scenario["content_type"]}
                    mock_request.body = AsyncMock(return_value=scenario["body"].encode())

                    self.create_object = self.api_server.create_object("links")

                    print(scenario["body"])
                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()

        
        self.run_async(async_test())

    def test_create_object(self):
        """
        Test the general object creation functionality for all supported object types.
        """
        async def async_test():

            for object_type, object_class in ALL_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    # Create a mock request
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": "application/json"}
                    test_object_spec = {"metadata": {"name": f"test_{object_type}"}}
                    mock_request.body = AsyncMock(return_value=json.dumps(test_object_spec).encode())
                    self.mock_etcd_client_instance.read_prefix.return_value = []
                    create_func = self.api_server.create_object(object_type)
                    created_object = await create_func(mock_request)
                    # Check if the created object is an instance of the correct class
                    self.assertIsInstance(created_object, object_class)
                    namespace = DEFAULT_NAMESPACE
                    link_header = f"{object_type}/{namespace}" if object_type in NAMESPACED_OBJECTS else object_type
                    # Verify that etcd_client.write was called with correct arguments
                    expected_call_args = (f"{link_header}/{test_object_spec['metadata']['name']}", created_object.model_dump(mode="json"))
                    self.mock_etcd_client_instance.write.assert_called_once_with(*expected_call_args)
                    self.mock_etcd_client_instance.reset_mock()
            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                invalid_type_func = self.api_server.create_object("invalid_type")
                await invalid_type_func(mock_request)
            self.assertEqual(context.exception.status_code, 400)

            
        self.run_async(async_test())

    def test_list_objects(self):
        """
        Test the listing of objects functionality, including handling of invalid object types and the 'watch' parameter.
        """
        async def async_test():

            # Test successful listing
            for object_type, object_class in ALL_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    mock_response = [{"kind": "Job", "metadata": {"name": f"test_{object_type}_1"}}, {"kind": "Job", "metadata": {"name": f"test_{object_type}_2"}}]
                    self.mock_etcd_client_instance.read_prefix.return_value = mock_response

                    listed_objects = self.api_server.list_objects(object_type, watch=False)
                    self.assertEqual(listed_objects.kind, object_class.__name__ + "List")
                    self.assertEqual(len(listed_objects.objects), len(mock_response))

                    self.mock_etcd_client_instance.reset_mock()

            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                self.api_server.list_objects("invalid_type", watch=False)
            self.assertEqual(context.exception.status_code, 400)

            # Test watch functionality
            mock_events = [("MODIFIED", {"metadata": {"name": "test_watch_1"}}), ("ADDED", {"metadata": {"name": "test_watch_2"}})]
            self.mock_etcd_client_instance.watch.return_value = (mock_events, lambda: None)

            response = self.api_server.list_objects("jobs", watch=True)
            self.assertIsInstance(response, StreamingResponse)

        
        self.run_async(async_test())

    def test_list_objects_extended(self):
        """
        Extended tests for the list_objects functionality, covering various scenarios like empty responses and different namespaces.
        """
        async def async_test():
            # Test empty response from etcd_client
            for object_type in ALL_OBJECTS:
                self.mock_etcd_client_instance.read_prefix.return_value = []
                obj_list = self.api_server.list_objects(object_type, watch=False)
                self.assertEqual(len(obj_list.objects), 0)
                self.mock_etcd_client_instance.reset_mock()

            # Test different namespaces
            for namespace in ["namespace1", "namespace2"]:
                self.mock_etcd_client_instance.read_prefix.return_value = [{"kind": "Job", "metadata": {"name": f"test_{namespace}"}}]
                for object_type in NAMESPACED_OBJECTS:
                    obj_list = self.api_server.list_objects(object_type, namespace=namespace, watch=False)
                    self.assertEqual(len(obj_list.objects), 1)
                    self.mock_etcd_client_instance.reset_mock()

            # Test watch parameter with events
            self.mock_etcd_client_instance.watch.return_value = ([("PUT", {"metadata": {"name": "test_job"}})], lambda: None)
            watch_response = self.api_server.list_objects("jobs", watch=True)
            self.assertIsInstance(watch_response, StreamingResponse)

        self.run_async(async_test())

    def test_get_object(self):
        """
        Test the retrieval of objects functionality, including handling of invalid object types and the 'watch' parameter.
        """
        async def async_test():

            # Test valid object retrieval
            for object_type, object_class in ALL_OBJECTS.items():
                object_name = f"test_{object_type}_name"
                namespace = DEFAULT_NAMESPACE if object_type in NAMESPACED_OBJECTS else None
                mock_object_data = {"metadata": {"name": object_name}}

                self.mock_etcd_client_instance.read.return_value = mock_object_data
                retrieved_object =  self.api_server.get_object(object_type, object_name, namespace, watch=False)
                self.assertIsInstance(retrieved_object, object_class)

                self.mock_etcd_client_instance.reset_mock()

            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                 self.api_server.get_object("invalid_type", "name")
            self.assertEqual(context.exception.status_code, 400)

            # Test object not found
            self.mock_etcd_client_instance.read.return_value = None
            with self.assertRaises(HTTPException) as context:
                 self.api_server.get_object("jobs", "non_existent", watch=False)
            self.assertEqual(context.exception.status_code, 404)

            # Test the 'watch' parameter behavior
            self.mock_etcd_client_instance.watch.return_value = ([], lambda: None)
            watch_response =  self.api_server.get_object("jobs", "test_job", watch=True)
            self.assertIsInstance(watch_response, StreamingResponse)

        self.run_async(async_test())

    def test_get_object_extended(self):
        """
        Extended tests for the get_object functionality, covering various scenarios like different object names and complex object data.
        """
        async def async_test():
            # 1. Test Different Namespaces
            for namespace in ["namespace1", "namespace2"]:
                self.mock_etcd_client_instance.read.return_value = {"metadata": {"name": f"test_object_{namespace}"}}
                obj =  self.api_server.get_object("jobs", "test_object", namespace, watch=False)
                self.assertIsNotNone(obj)

            # 2. Test Object Name Variations
            object_names = ["a", "special_@object!", "123"]
            for name in object_names:
                self.mock_etcd_client_instance.read.return_value = {"metadata": {"name": name}}
                obj =  self.api_server.get_object("jobs", name, watch=False)
                self.assertIsNotNone(obj)

            # 2.1 Test Invalid Object Names
            object_names = ["", 123]
            for name in object_names:
                self.mock_etcd_client_instance.read.return_value = {"metadata": {"name": name}}
                with self.assertRaises(ValidationError):
                    self.api_server.get_object("jobs", name, watch=False)

            # 3. Test Watch Parameter with Event Generation
            self.mock_etcd_client_instance.watch.return_value = ([("PUT", {"metadata": {"name": "watched_object"}})], lambda: None)
            watch_response =  self.api_server.get_object("jobs", "watched_object", watch=True)
            self.assertIsInstance(watch_response, StreamingResponse)

            # 4. Test with Complex Object Data
            complex_data = {
                "metadata": {"name": "complex_object"},
                "spec": {
                    "key": "value", #Should be ignored
                    "image": "ubuntu:latest",
                    "resources": {"cpus": 1.0, "memory": 0.0},
                    "run": "",
                    "envs": {},
                    "ports": [],
                    "replicas": 1,
                    "restart_policy": "Always"
                }
            }
            self.mock_etcd_client_instance.read.return_value = complex_data
            obj =  self.api_server.get_object("jobs", "complex_object", watch=False)
            self.assertEqual(obj.metadata.name, complex_data["metadata"]["name"])
            self.assertEqual(obj.spec.image, complex_data["spec"]["image"])
            self.assertEqual(obj.spec.resources, complex_data["spec"]["resources"])
            self.assertEqual(obj.spec.run, complex_data["spec"]["run"])
            self.assertEqual(obj.spec.envs, complex_data["spec"]["envs"])
            self.assertEqual(obj.spec.ports, complex_data["spec"]["ports"])
            self.assertEqual(obj.spec.replicas, complex_data["spec"]["replicas"])
            self.assertEqual(obj.spec.restart_policy, complex_data["spec"]["restart_policy"])
            with self.assertRaises(AttributeError):
                obj.spec.key

            # 5. Test Retrieval of Non-Namespaced Objects
            self.mock_etcd_client_instance.read.return_value = {"metadata": {"name": "non_namespaced_object"}}
            obj =  self.api_server.get_object("clusters", "non_namespaced_object", watch=False)
            self.assertIsNotNone(obj)

            # 6. Test Invalid Object Names
            self.mock_etcd_client_instance.read.return_value = None
            with self.assertRaises(HTTPException):
                 self.api_server.get_object("jobs", "invalid_name", watch=False)

            # 7. Test Handling of Partial Object Data
            partial_data = {"metadata": {"name": "partial_object"}}
            self.mock_etcd_client_instance.read.return_value = partial_data
            obj =  self.api_server.get_object("jobs", "partial_object", watch=False)
            self.assertIsNotNone(obj)

        self.run_async(async_test())

    def test_update_object(self):
        """
        Test the object update functionality for all supported object types, including handling of non-existing and invalid objects.
        """
        async def async_test():
            # Test update for each object type
            for object_type, object_class in ALL_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": "application/json"}
                    test_object_spec = {"metadata": {"name": f"test_{object_type}"}}
                    mock_request.body = AsyncMock(return_value=json.dumps(test_object_spec).encode())

                    # Mock etcd_client to simulate existing object
                    self.mock_etcd_client_instance.read_prefix.return_value = [{"metadata": {"name": f"test_{object_type}"}}]
                    update_func = self.api_server.update_object(object_type)
                    updated_object = await update_func(mock_request)
                    self.mock_etcd_client_instance.update.assert_called_once()
                    self.assertIsInstance(updated_object, object_class)

                    self.mock_etcd_client_instance.reset_mock()

            # Test handling of non-existing objects
            self.mock_etcd_client_instance.read_prefix.return_value = []
            with self.assertRaises(HTTPException) as context:
                await update_func(mock_request)
            self.assertEqual(context.exception.status_code, 400)

            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                invalid_update_func = self.api_server.update_object("invalid_type")
                await invalid_update_func(mock_request)
            self.assertEqual(context.exception.status_code, 400)

            # Test exception handling during etcd client update
            self.mock_etcd_client_instance.read_prefix.return_value = [{"metadata": {"name": f"test_{object_type}"}}]
            self.mock_etcd_client_instance.update.side_effect = Exception("Etcd client error")
            with self.assertRaises(HTTPException) as context:
                await update_func(mock_request)
            self.assertEqual(context.exception.status_code, 409)

        self.run_async(async_test())

    def test_delete_object(self):
        """
        Test the object deletion functionality for all supported object types, including handling of non-existing objects.
        """
        async def async_test():
            for object_type, _ in ALL_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    object_name = f"test_{object_type}"
                    is_namespaced = object_type in NAMESPACED_OBJECTS
                    namespace = DEFAULT_NAMESPACE if is_namespaced else None
                    link_header = f"{object_type}/{namespace}" if namespace else object_type

                    self.mock_etcd_client_instance.delete.return_value = {"metadata": {"name": object_name}}
                    delete_func = self.api_server.delete_object
                    deleted_obj_dict = delete_func(object_type, object_name, namespace, is_namespaced)
                    self.assertEqual(deleted_obj_dict["metadata"]["name"], object_name)
                    self.mock_etcd_client_instance.delete.assert_called_once_with(f"{link_header}/{object_name}")

                    self.mock_etcd_client_instance.reset_mock()

            # Test handling of non-existing objects
            self.mock_etcd_client_instance.delete.return_value = None
            with self.assertRaises(HTTPException) as context:
                delete_func("jobs", "non_existing_object")
            self.assertEqual(context.exception.status_code, 400)

        self.run_async(async_test())

if __name__ == '__main__':
    unittest.main()
