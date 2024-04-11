import asyncio
import json
import unittest
from copy import deepcopy
from typing import Any, Callable, Coroutine, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import yaml
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from api_server import launch_server
from skyflow.etcd_client.etcd_client import KeyNotFoundError
from skyflow.globals_object import ALL_OBJECTS, NAMESPACED_OBJECTS
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.templates import Namespace, NamespaceMeta

launch_server.check_and_install_etcd()

from api_server.api_server import APIServer


def apply_modification(base, path, value):
    """
    Recursively navigate through the path to apply the modification.
    """
    current_level = base
    for i, key in enumerate(path):
        if i == len(
                path
        ) - 1:  # If it's the last element in the path, apply the value
            if isinstance(current_level, list):
                # For lists, the key should be the index
                current_level[key] = value
            else:
                current_level[key] = value
        else:
            if isinstance(current_level, list):
                current_level = current_level[key]
            else:
                current_level = current_level.setdefault(key, {})
    return base


class TestAPIServer(unittest.TestCase):

    @patch('api_server.api_server.ETCDClient')
    @patch('api_server.api_server.APIServer._authenticate_action')
    def setUp(self, mock_authenticate_action, mock_etcd_client):
        """
        Set up the test environment by mocking the ETCDClient and 
        initializing the APIServer.
        """
        self.mock_etcd_client_instance = mock_etcd_client.return_value
        self.api_server = APIServer(app="test")
        self.api_server._authenticate_action = MagicMock(return_value=True)
        self.api_server._check_cluster_connectivity = MagicMock(
            return_value=True)

    def run_async(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """
        Utility method to run the coroutine and manage the event loop.
        """
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_create_object_with_different_headers(self):
        """
        Test the creation of objects with different content types in request headers.
        """

        async def async_test():
            # Base request setup
            base_request = {
                "headers": {
                    "content-type": "application/json"
                },
                "body": json.dumps({"metadata": {
                    "name": "test-object"
                }})
            }

            # Define modifications to the base request for different scenarios
            modifications = [{
                "update": {
                    "headers": {
                        "content-type": "application/json"
                    },
                    "body":
                    json.dumps({"metadata": {
                        "name": "json-test-object"
                    }})
                },
                "expected_success": True
            }, {
                "update": {
                    "headers": {
                        "content-type": "application/yaml"
                    },
                    "body":
                    yaml.dump({"metadata": {
                        "name": "yaml-test-object"
                    }})
                },
                "expected_success": True
            }, {
                "update": {
                    "headers": {
                        "content-type": "text/plain"
                    },
                    "body": "plain text"
                },
                "expected_success": False
            }]

            for modification in modifications:
                # Copy the base request and apply the modification
                test_request = deepcopy(base_request)
                test_request.update(modification["update"])

                with self.subTest(modification=modification):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = test_request["headers"]
                    mock_request.body = AsyncMock(
                        return_value=test_request["body"].encode())

                    self.create_object = self.api_server.create_object("jobs")

                    if modification["expected_success"]:
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        self.mock_etcd_client_instance.write.reset_mock()
                    else:
                        with self.assertRaises(HTTPException):
                            await self.create_object(mock_request)

        self.run_async(async_test())

    async def execute_tests(self, create_object_func: Callable[[Request],
                                                               Coroutine[None,
                                                                         None,
                                                                         Any]],
                            base_spec: Dict[str, Any],
                            modifications: List[Dict[str, Any]]) -> None:
        """
        Tests the creation of objects with various specifications, including invalid specs.
        This function dynamically generates test scenarios based on a base specification and a list of modifications to apply.

        :param create_object_func: The coroutine function to be tested, which creates the object.
        :param base_spec: The base specification dictionary for creating a valid object.
        :param modifications: A list of modifications, where each modification is a dictionary containing
                            the 'path' for the specification to modify, the 'value' to set, and the
                            'expected_exception' if the test should expect an exception.
        """
        scenarios = []
        for modification in modifications:
            # Create a copy of the base spec and apply the modification
            test_spec = deepcopy(base_spec)
            if modification["path"]:  # Check if path needs modification
                test_spec = apply_modification(test_spec, modification["path"],
                                               modification["value"])

            scenario = {
                "content_type": "application/json",
                "body": json.dumps(test_spec),
                "expected_exception": modification["exception"]
            }
            scenarios.append(scenario)

        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                mock_request = MagicMock(spec=Request)
                mock_request.headers = {"content-type": "application/json"}
                mock_request.body = AsyncMock(
                    return_value=scenario["body"].encode())

                if scenario["expected_exception"]:
                    with self.assertRaises(scenario["expected_exception"]):
                        await create_object_func(mock_request)
                else:
                    await create_object_func(mock_request)

    def test_job_creation_with_different_specs(self):
        """
        Test the creation of Job objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid job specification
            base_spec = {
                "metadata": {
                    "name": "valid-job-name"
                },
                "spec": {
                    "replicas": 1,
                    "resources": {
                        "cpus": 1,
                        "memory": 1024
                    },
                    "image": "ubuntu:latest",
                    "envs": {
                        "VAR1": "value1"
                    },
                    "ports": [80],
                    "restart_policy": "Always",
                    "run": "echo Hello World"
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "replicas"],
                    "value": 0,
                    "exception": ValueError
                },
                {
                    "path": ["spec", "replicas"],
                    "value": -1,
                    "exception": ValueError
                },
                {
                    "path": ["spec", "replicas"],
                    "value": "invalid",
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "resources", "cpus"],
                    "value": -1,
                    "exception": ValueError
                },
                {
                    "path": ["spec", "resources", "memory"],
                    "value": -100,
                    "exception": ValueError
                },
                {
                    "path": ["spec", "resources", "GPU"],
                    "value": -2,
                    "exception": ValueError
                },
                {
                    "path": ["spec", "resources", "GPU"],
                    "value": "two",
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "image"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["spec", "image"],
                    "value": 123,
                    "exception": ValidationError
                },
                # Valid cases
                {
                    "path": ["spec", "image"],
                    "value": "ubuntu:latest",
                    "exception": None
                },
                {
                    "path": ["spec", "image"],
                    "value": "alex/personal/repo/path/cool-image:latest",
                    "exception": None
                },
                # Environment variables validation with invalid types
                {
                    "path": ["spec", "envs"],
                    "value": {
                        "VAR1": None
                    },
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "envs"],
                    "value": {
                        "VAR1": 123
                    },
                    "exception": ValidationError
                },
                # Environment variable with empty string (valid case)
                {
                    "path": ["spec", "envs"],
                    "value": {
                        "VAR1": ""
                    },
                    "exception": None
                },

                # Ports validation
                {
                    "path": ["spec", "ports"],
                    "value": [-1],
                    "exception": ValueError
                },
                {
                    "path": ["spec", "ports"],
                    "value": [0],
                    "exception": ValueError
                },
                {
                    "path": ["spec", "ports"],
                    "value": [70000],
                    "exception": ValueError
                },
                {
                    "path": ["spec", "ports"],
                    "value": ["invalid"],
                    "exception": ValidationError
                },
                # Valid ports case
                {
                    "path": ["spec", "ports"],
                    "value": [8080],
                    "exception": None
                },

                # Restart policy validation
                {
                    "path": ["spec", "restart_policy"],
                    "value": "InvalidPolicy",
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "restart_policy"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["spec", "restart_policy"],
                    "value": 123,
                    "exception": ValidationError
                },
                # Valid restart policy case
                {
                    "path": ["spec", "restart_policy"],
                    "value": "Never",
                    "exception": None
                },

                # Run command validation
                {
                    "path": ["spec", "run"],
                    "value": 123,
                    "exception": ValidationError
                },
            ]

            await self.execute_tests(self.api_server.create_object("jobs"),
                                     base_spec, modifications)

        self.run_async(async_test())

    def test_filter_policy_creation_with_various_specs(self):
        """
        Test the creation of FilterPolicy objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid FilterPolicy specification
            base_spec = {
                "metadata": {
                    "name": "valid-policy"
                },
                "spec": {
                    "cluster_filter": {
                        "include": ["clusterA"],
                        "exclude": ["clusterB"]
                    },
                    "labels_selector": {
                        "key": "value"
                    }
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                # Metadata name tests
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },

                # ClusterFilter include/exclude tests
                {
                    "path": ["spec", "cluster_filter", "include"],
                    "value": -1,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "cluster_filter", "exclude"],
                    "value": {
                        "clusterC": "value"
                    },
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "cluster_filter", "include"],
                    "value": ["", "clusterA"],
                    "exception": ValidationError
                },  # Include list with empty string
                {
                    "path": ["spec", "cluster_filter", "exclude"],
                    "value": ["clusterB", ""],
                    "exception": ValidationError
                },  # Exclude list with empty string

                # Labels selector tests
                {
                    "path": ["spec", "labels_selector"],
                    "value": {
                        "key": 123
                    },
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "labels_selector"],
                    "value": {
                        "": "value"
                    },
                    "exception": ValidationError
                },  # Empty key
                {
                    "path": ["spec", "labels_selector"],
                    "value": {
                        "key": ""
                    },
                    "exception": ValidationError
                },  # Empty value

                # Valid cases with different configurations
                {
                    "path": [],
                    "value": None,
                    "exception": None
                },  # No modification, valid base case
                {
                    "path": ["spec", "cluster_filter", "include"],
                    "value": ["clusterA", "clusterB"],
                    "exception": None
                },  # Valid include clusters
                {
                    "path": ["spec", "cluster_filter", "exclude"],
                    "value": ["clusterC", "clusterD"],
                    "exception": None
                },  # Valid exclude clusters
            ]

            await self.execute_tests(
                self.api_server.create_object("filterpolicies"), base_spec,
                modifications)

        self.run_async(async_test())

    def test_service_creation_with_various_specs(self):
        """
        Test the creation of Service objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid Service specification
            base_spec = {
                "metadata": {
                    "name": "valid-service"
                },
                "spec": {
                    "type": "ClusterIP",
                    "ports": [{
                        "port": 80,
                        "target_port": 80
                    }]
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "type"],
                    "value": "InvalidType",
                    "exception": ValueError
                },
                {
                    "path": ["spec", "type"],
                    "value": None,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "ports", 0, "port"],
                    "value": -1,
                    "exception": ValueError
                },
                {
                    "path": ["spec", "ports", 0, "target_port"],
                    "value": "invalid",
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "cluster_ip"],
                    "value": -1,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "primary_cluster"],
                    "value": -1,
                    "exception": ValidationError
                },
                # Valid case
                {
                    "path": [],
                    "value": None,
                    "exception": None
                }  # Represents no modification, valid case
            ]

            await self.execute_tests(self.api_server.create_object("services"),
                                     base_spec, modifications)

        self.run_async(async_test())

    def test_endpoints_creation_with_various_specs(self):
        """
        Test the creation of Endpoints objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid Endpoints specification
            base_spec = {
                "metadata": {
                    "name": "valid-endpoints"
                },
                "spec": {
                    "selector": {
                        "key": "value"
                    },
                    "endpoints": {
                        "clusterA": {
                            "num_endpoints": 2,
                            "exposed_to_cluster": True
                        }
                    },
                    "primary_cluster": "clusterA"
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "selector", "key"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "endpoints", "clusterA", "num_endpoints"],
                    "value": -1,
                    "exception": ValueError
                },
                {
                    "path":
                    ["spec", "endpoints", "clusterA", "exposed_to_cluster"],
                    "value": "invalid",
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "primary_cluster"],
                    "value": -1,
                    "exception": ValidationError
                },
                # Valid case
                {
                    "path": [],
                    "value": None,
                    "exception": None
                }  # Represents no modification, valid case
            ]

            await self.execute_tests(
                self.api_server.create_object("endpoints"), base_spec,
                modifications)

        self.run_async(async_test())

    def test_cluster_creation_with_various_specs(self):
        """
        Test the creation of Cluster objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid Cluster specification
            base_spec = {
                "metadata": {
                    "name": "valid-cluster"
                },
                "spec": {
                    "manager": "k8"
                },
                "status": {
                    "status": "READY",
                    "capacity": {
                        "nodeA": {
                            "cpus": 2,
                            "memory": 2048
                        }
                    },
                    "allocatable_capacity": {
                        "nodeA": {
                            "cpus": 2,
                            "memory": 2048
                        }
                    },
                    "accelerator_types": {
                        "nodeA": "GPU"
                    }
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "manager"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["spec", "manager"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["status", "status"],
                    "value": "INVALID_STATUS",
                    "exception": ValueError
                },
                {
                    "path": ["status", "status"],
                    "value": None,
                    "exception": ValidationError
                },
                {
                    "path": ["status", "capacity", "nodeA", "cpus"],
                    "value": -1,
                    "exception": ValueError
                },
                {
                    "path": ["status", "capacity", "nodeA", "GPU"],
                    "value": "invalid",
                    "exception": ValidationError
                },
                {
                    "path":
                    ["status", "allocatable_capacity", "nodeA", "MEMORY"],
                    "value": -100,
                    "exception": ValueError
                },
                {
                    "path":
                    ["status", "allocatable_capacity", "nodeA", "ACCELERATOR"],
                    "value":
                    "invalid",
                    "exception":
                    ValidationError
                },
                {
                    "path": ["status", "accelerator_types", "nodeA"],
                    "value": -1,
                    "exception": ValidationError
                },
                # Valid case
                {
                    "path": [],
                    "value": None,
                    "exception": None
                }  # Represents no modification, valid case
            ]

            await self.execute_tests(self.api_server.create_object("clusters"),
                                     base_spec, modifications)

        self.run_async(async_test())

    def test_namespace_creation_with_various_specs(self):
        """
        Test the creation of Namespace objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid Namespace specification
            base_spec = {
                "metadata": {
                    "name": "valid-namespace"
                },
                "status": {
                    "status": "ACTIVE"
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["status", "status"],
                    "value": "INVALID_STATUS",
                    "exception": ValueError
                },
                {
                    "path": ["status", "status"],
                    "value": None,
                    "exception": ValidationError
                },
            ]

            await self.execute_tests(
                self.api_server.create_object("namespaces"), base_spec,
                modifications)

        self.run_async(async_test())

    def test_link_creation_with_various_specs(self):
        """
        Test the creation of Link objects with various specifications, including invalid specs.
        """

        async def async_test():
            # Base valid Link specification
            base_spec = {
                "metadata": {
                    "name": "valid-link"
                },
                "spec": {
                    "source_cluster": "clusterA",
                    "target_cluster": "clusterB"
                },
                "status": {
                    "phase": "ACTIVE"
                }
            }

            # Scenarios with modifications to the base spec for testing various validations
            modifications = [
                {
                    "path": ["metadata", "name"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["metadata", "name"],
                    "value": 123,
                    "exception": ValidationError
                },
                {
                    "path": ["spec", "source_cluster"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["spec", "target_cluster"],
                    "value": "",
                    "exception": ValueError
                },
                {
                    "path": ["status", "phase"],
                    "value": "INVALID_PHASE",
                    "exception": ValueError
                },
                {
                    "path": ["status", "phase"],
                    "value": None,
                    "exception": ValidationError
                },
            ]

            await self.execute_tests(self.api_server.create_object("links"),
                                     base_spec, modifications)

        self.run_async(async_test())

    def test_create_object(self):
        """
        Test the general object creation functionality for all supported object types.
        """

        async def async_test():

            for object_type, object_class in NAMESPACED_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    # Create a mock request
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": "application/json"}
                    test_object_spec = {
                        "metadata": {
                            "name": f"test-{object_type}"
                        }
                    }
                    mock_request.body = AsyncMock(
                        return_value=json.dumps(test_object_spec).encode())
                    self.mock_etcd_client_instance.read_prefix.return_value = []
                    create_func = self.api_server.create_object(object_type)
                    created_object = await create_func(mock_request)
                    # Check if the created object is an instance of the correct class
                    self.assertIsInstance(created_object, object_class)
                    namespace = DEFAULT_NAMESPACE
                    link_header = f"{object_type}/{namespace}" if object_type in NAMESPACED_OBJECTS else object_type
                    # Verify that etcd_client.write was called with correct arguments
                    expected_call_args = (
                        f"{link_header}/{test_object_spec['metadata']['name']}",
                        created_object.model_dump(mode="json"))
                    self.mock_etcd_client_instance.write.assert_called_once_with(
                        *expected_call_args)
                    self.mock_etcd_client_instance.reset_mock()
            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                invalid_type_func = self.api_server.create_object(
                    "invalid_type")
                await invalid_type_func(mock_request)
            self.assertEqual(context.exception.status_code, 400)

        self.run_async(async_test())

    def test_list_objects(self):
        """
        Test the listing of objects functionality, including handling of invalid object types and the 'watch' parameter.
        """

        async def async_test():

            # Test successful listing
            for object_type, object_class in NAMESPACED_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    mock_response = [{
                        "kind": "Job",
                        "metadata": {
                            "name": f"test-{object_type}-1"
                        }
                    }, {
                        "kind": "Job",
                        "metadata": {
                            "name": f"test-{object_type}-2"
                        }
                    }]
                    self.mock_etcd_client_instance.read_prefix.return_value = mock_response

                    listed_objects = self.api_server.list_objects(object_type,
                                                                  watch=False)
                    self.assertEqual(listed_objects.kind,
                                     object_class.__name__ + "List")
                    self.assertEqual(len(listed_objects.objects),
                                     len(mock_response))

                    self.mock_etcd_client_instance.reset_mock()

            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                self.api_server.list_objects("invalid_type", watch=False)
            self.assertEqual(context.exception.status_code, 400)

        self.run_async(async_test())

    def test_list_objects_extended(self):
        """
        Extended tests for the list_objects functionality, covering various scenarios like empty responses and different namespaces.
        """

        async def async_test():
            # Test empty response from etcd_client
            for object_type in NAMESPACED_OBJECTS:
                self.mock_etcd_client_instance.read_prefix.return_value = []
                obj_list = self.api_server.list_objects(object_type,
                                                        watch=False)
                self.assertEqual(len(obj_list.objects), 0)
                self.mock_etcd_client_instance.reset_mock()

            # Test different namespaces
            for namespace in ["namespace1", "namespace2"]:
                self.mock_etcd_client_instance.read_prefix.return_value = [{
                    "kind":
                    "Job",
                    "metadata": {
                        "name": f"test-{namespace}"
                    }
                }]
                for object_type in NAMESPACED_OBJECTS:
                    obj_list = self.api_server.list_objects(
                        object_type, namespace=namespace, watch=False)
                    self.assertEqual(len(obj_list.objects), 1)
                    self.mock_etcd_client_instance.reset_mock()

        self.run_async(async_test())

    def test_get_object(self):
        """
        Test the retrieval of objects functionality, including handling of invalid object types and the 'watch' parameter.
        """

        async def async_test():

            # Test valid object retrieval
            for object_type, object_class in NAMESPACED_OBJECTS.items():
                object_name = f"test-{object_type}-name"
                namespace = DEFAULT_NAMESPACE if object_type in NAMESPACED_OBJECTS else None
                mock_object_data = {"metadata": {"name": object_name}}

                self.mock_etcd_client_instance.read.return_value = mock_object_data
                retrieved_object = self.api_server.get_object(object_type,
                                                              object_name,
                                                              namespace,
                                                              watch=False)
                self.assertIsInstance(retrieved_object, object_class)

                self.mock_etcd_client_instance.reset_mock()

            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                self.api_server.get_object("invalid_type", "name")
            self.assertEqual(context.exception.status_code, 400)

            # Test object not found
            self.mock_etcd_client_instance.read.return_value = None
            with self.assertRaises(HTTPException) as context:
                self.api_server.get_object("jobs", "non-existent", watch=False)
            self.assertEqual(context.exception.status_code, 404)

        self.run_async(async_test())

    def test_get_object_extended(self):
        """
        Extended tests for the get_object functionality, covering various scenarios like different object names and complex object data.
        """

        async def async_test():
            # 1. Test Different Namespaces
            for namespace in ["namespace1", "namespace2"]:
                self.mock_etcd_client_instance.read.return_value = {
                    "metadata": {
                        "name": f"test-object-{namespace}"
                    }
                }
                obj = self.api_server.get_object("jobs",
                                                 "test-object",
                                                 namespace,
                                                 watch=False)
                self.assertIsNotNone(obj)

            # 2. Test Object Name Variations
            object_names = ["a", "special-object", "123"]
            for name in object_names:
                self.mock_etcd_client_instance.read.return_value = {
                    "metadata": {
                        "name": name
                    }
                }
                obj = self.api_server.get_object("jobs", name, watch=False)
                self.assertIsNotNone(obj)

            # 2.1 Test Invalid Object Names
            object_names = ["", 123]
            for name in object_names:
                self.mock_etcd_client_instance.read.return_value = {
                    "metadata": {
                        "name": name
                    }
                }
                with self.assertRaises(ValidationError):
                    self.api_server.get_object("jobs", name, watch=False)

            # 3. Test Watch Parameter with Event Generation
            self.mock_etcd_client_instance.watch.return_value = ([("PUT", {
                "metadata": {
                    "name": "watched-object"
                }
            })], lambda: None)
            watch_response = self.api_server.get_object("jobs",
                                                        "watched-object",
                                                        namespace=namespace,
                                                        watch=True)
            link_header = f"{'jobs'}/{namespace}" if namespace else "jobs"
            self.mock_etcd_client_instance.watch.assert_called_once_with(
                f"{link_header}/{'watched-object'}")
            self.assertIsInstance(watch_response, StreamingResponse)

            # 4. Test with Complex Object Data
            complex_data = {
                "metadata": {
                    "name": "complex-object"
                },
                "spec": {
                    "key": "value",  #Should be ignored
                    "image": "ubuntu:latest",
                    "resources": {
                        "cpus": 1.0,
                        "memory": 0.0
                    },
                    "run": "",
                    "envs": {},
                    "ports": [],
                    "replicas": 1,
                    "restart_policy": "Always"
                }
            }
            self.mock_etcd_client_instance.read.return_value = complex_data
            obj = self.api_server.get_object("jobs",
                                             "complex-object",
                                             watch=False)
            self.assertEqual(obj.metadata.name,
                             complex_data["metadata"]["name"])
            self.assertEqual(obj.spec.image, complex_data["spec"]["image"])
            self.assertEqual(obj.spec.resources,
                             complex_data["spec"]["resources"])
            self.assertEqual(obj.spec.run, complex_data["spec"]["run"])
            self.assertEqual(obj.spec.envs, complex_data["spec"]["envs"])
            self.assertEqual(obj.spec.ports, complex_data["spec"]["ports"])
            self.assertEqual(obj.spec.replicas,
                             complex_data["spec"]["replicas"])
            self.assertEqual(obj.spec.restart_policy,
                             complex_data["spec"]["restart_policy"])
            with self.assertRaises(AttributeError):
                obj.spec.key

            # 5. Test Retrieval of Non-Namespaced Objects
            self.mock_etcd_client_instance.read.return_value = {
                "metadata": {
                    "name": "non-namespaced-object"
                }
            }
            obj = self.api_server.get_object("clusters",
                                             "non-namespaced-object",
                                             watch=False)
            self.assertIsNotNone(obj)

            # 6. Test Invalid Object Names
            self.mock_etcd_client_instance.read.return_value = None
            with self.assertRaises(HTTPException):
                self.api_server.get_object("jobs", "invalid_name", watch=False)

            # 7. Test Handling of Partial Object Data
            partial_data = {"metadata": {"name": "partial-object"}}
            self.mock_etcd_client_instance.read.return_value = partial_data
            obj = self.api_server.get_object("jobs",
                                             "partial-object",
                                             watch=False)
            self.assertIsNotNone(obj)

        self.run_async(async_test())

    def test_update_object(self):
        """
        Test the object update functionality for all supported object types, including handling of non-existing and invalid objects.
        """

        async def async_test():
            # Test update for each object type
            for object_type, object_class in NAMESPACED_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    mock_request = MagicMock(spec=Request)
                    mock_request.headers = {"content-type": "application/json"}
                    test_object_spec = {
                        "metadata": {
                            "name": f"test-{object_type}"
                        }
                    }
                    mock_request.body = AsyncMock(
                        return_value=json.dumps(test_object_spec).encode())

                    # Mock etcd_client to simulate existing object
                    self.mock_etcd_client_instance.read_prefix.return_value = [
                        {
                            "metadata": {
                                "name": f"test-{object_type}"
                            }
                        }
                    ]
                    update_func = self.api_server.update_object(object_type)
                    updated_object = await update_func(mock_request)
                    self.mock_etcd_client_instance.update.assert_called_once()
                    self.assertIsInstance(updated_object, object_class)

                    self.mock_etcd_client_instance.reset_mock()

            # Test handling of non-existent objects
            self.mock_etcd_client_instance.read_prefix.return_value = []
            with self.assertRaises(HTTPException) as context:
                await update_func(mock_request)
            self.assertEqual(context.exception.status_code, 400)

            # Test handling of invalid object type
            with self.assertRaises(HTTPException) as context:
                invalid_update_func = self.api_server.update_object(
                    "invalid_type")
                await invalid_update_func(mock_request)
            self.assertEqual(context.exception.status_code, 400)

            # Test exception handling during etcd client update
            self.mock_etcd_client_instance.read_prefix.return_value = [{
                "metadata": {
                    "name": f"test-{object_type}"
                }
            }]
            self.mock_etcd_client_instance.update.side_effect = KeyNotFoundError(
                "Etcd client error")
            with self.assertRaises(HTTPException) as context:
                await update_func(mock_request)
            self.assertEqual(context.exception.status_code, 404)

        self.run_async(async_test())

    def test_delete_object(self):
        """
        Test the object deletion functionality for all supported object types, including handling of non-existing objects.
        """

        async def async_test():
            for object_type, _ in NAMESPACED_OBJECTS.items():
                with self.subTest(object_type=object_type):
                    object_name = f"test-{object_type}"
                    is_namespaced = object_type in NAMESPACED_OBJECTS
                    namespace = DEFAULT_NAMESPACE if is_namespaced else None
                    link_header = f"{object_type}/{namespace}" if namespace else object_type

                    self.mock_etcd_client_instance.delete.return_value = {
                        "metadata": {
                            "name": object_name
                        }
                    }
                    delete_func = self.api_server.delete_object
                    deleted_obj_dict = delete_func(object_type, object_name,
                                                   namespace)
                    self.assertEqual(deleted_obj_dict["metadata"]["name"],
                                     object_name)
                    self.mock_etcd_client_instance.delete.assert_called_once_with(
                        f"{link_header}/{object_name}")

                    self.mock_etcd_client_instance.reset_mock()

            # Test handling of non-existent objects
            self.mock_etcd_client_instance.delete.return_value = None
            with self.assertRaises(HTTPException) as context:
                delete_func("jobs", "non_existing_object")
            self.assertEqual(context.exception.status_code, 400)

        self.run_async(async_test())


if __name__ == '__main__':
    unittest.main()
