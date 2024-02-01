import unittest
import json
from pydantic import ValidationError
import yaml
import asyncio

from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException

from api_server.api_server import APIServer, app
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.templates import Namespace, NamespaceMeta, ObjectException
from skyflow.templates.job_template import JobException

class TestAPIServer(unittest.TestCase):
    @patch('api_server.api_server.ETCDClient')
    def setUp(self, mock_etcd_client):
        # Mock the ETCDClient
        self.mock_etcd_client_instance = mock_etcd_client.return_value
        with patch.object(APIServer, '_post_init_hook', return_value=None):
            self.api_server = APIServer()
            
    def run_async(self, coro):
        """
        Utility method to run the coroutine and manage the event loop.
        """
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_post_init_hook_with_default_namespace(self):
        # Simulate that the default namespace already exists
        self.mock_etcd_client_instance.read_prefix.return_value = [DEFAULT_NAMESPACE]
        self.api_server._post_init_hook()
        # Assert that etcd_client.write was NOT called since the namespace exists
        self.mock_etcd_client_instance.write.assert_not_called()

    def test_post_init_hook_without_default_namespace(self):
        # Simulate that the default namespace does not exist
        self.mock_etcd_client_instance.read_prefix.return_value = []
        self.api_server._post_init_hook()
        expected_namespace = Namespace(metadata=NamespaceMeta(name="default")).model_dump(mode="json")
        # Assert that etcd_client.write was called since the namespace does NOT exists
        self.mock_etcd_client_instance.write.assert_called_with(
            "namespaces/default",
            expected_namespace
        )
    
    def test_create_object_with_various_configs(self):
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
                        # Attempt object creation and verify success
                        await self.create_object(mock_request)
                        self.mock_etcd_client_instance.write.assert_called()
                        # Reset mock to avoid counting previous calls in the next scenario
                        self.mock_etcd_client_instance.write.reset_mock()
                    else:
                        # Attempt object creation and expect failure (e.g., HTTPException)
                        with self.assertRaises(HTTPException):
                            await self.create_object(mock_request)

        # Run the asynchronous test using the utility method
        self.run_async(async_test())

    def test_job_creation_with_invalid_specs(self):
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

                    # Attempt object creation and expect an exception
                    print(scenario["body"])
                    if scenario["expected_exception"]:
                        with self.assertRaises(scenario["expected_exception"]):
                            await self.create_object(mock_request)
                    else:
                         await self.create_object(mock_request)
                         self.mock_etcd_client_instance.write.assert_called()

        # Run the asynchronous test using the utility method
        self.run_async(async_test())

if __name__ == '__main__':
    unittest.main()
