"""
Unit tests for the API client module.

To run the tests, use the following command:
pytest skyflow/tests/api_client_unit_tests.py

To run one specific test, use the following command:
pytest skyflow/tests/api_client_unit_tests.py::test_namespace_object_api_create_success

"""
import tempfile
from enum import Enum
from typing import Any, Dict, Generator, List, Tuple, Union

import pytest
import requests
from requests import Timeout
from unittest.mock import patch
from skyflow.api_client.object_api import (APIException, NamespaceObjectAPI,
                                           NoNamespaceObjectAPI)
from skyflow.tests.tests_utils import setup_skyflow, shutdown_skyflow


@pytest.fixture(scope="session", autouse=True)
def etcd_backup_and_restore():
    with tempfile.TemporaryDirectory() as temp_data_dir:
        with patch('api_server.api_server.API_SERVER_CONFIG_PATH', new=temp_data_dir + "/.skyconf/config.yaml"), \
            patch('skyflow.utils.utils.API_SERVER_CONFIG_PATH', new=temp_data_dir + "/.skyconf/config.yaml"):
            # Kill any running sky_manager processes
            shutdown_skyflow(temp_data_dir)
            setup_skyflow(temp_data_dir)

            yield  # Test execution happens here

            # Stop the application and ETCD server
            shutdown_skyflow(temp_data_dir)

            print("Cleaned up temporary ETCD data directory.")


class ResponseType(Enum):
    ERROR = "error"
    TIMEOUT = "timeout"
    BAD = "bad"
    SERVER_ERROR = "server-error"
    DEFAULT = "default"
    NO_NAMESPACE = "no-namespace"
    SELECTIVE_LIST = "selective-list"


class MockResponse:
    """A class to mock HTTP responses."""

    def __init__(self, json_data: Any, status_code: int) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Returns the mocked JSON data."""
        if self._json_data is not None:
            return self._json_data
        raise ValueError("No JSON content")


@pytest.fixture
def namespace_api() -> NamespaceObjectAPI:
    """Fixture to setup a NamespaceObjectAPI instance for testing."""
    namespace = "test-namespace"
    object_type = "test-object-type"
    api = NamespaceObjectAPI(namespace, object_type)
    api.host = "localhost"
    api.port = 8080
    return api


@pytest.fixture
def nonamespace_api() -> NoNamespaceObjectAPI:
    """Fixture to setup a NoNamespaceObjectAPI instance for testing."""
    object_type = "test-object-type"
    api = NoNamespaceObjectAPI(object_type)
    api.host = "localhost"
    api.port = 8080
    return api


@pytest.fixture
def mock_requests(monkeypatch: Any) -> None:
    """Fixture to mock HTTP requests using a predefined response map."""

    response_map: Dict[Tuple[str, ResponseType], Any] = {
        ("post", ResponseType.ERROR): ({
            "detail": "Error occurred"
        }, 404),
        ("post", ResponseType.TIMEOUT): ("timeout", None),
        ("post", ResponseType.BAD): ({
            "detail": "Bad request"
        }, 400),
        ("post", ResponseType.SERVER_ERROR): (None, 500),
        ("post", ResponseType.DEFAULT): ({
            "kind": "Job",
            "metadata": {
                "name": "test-job"
            }
        }, 200),
        ("put", ResponseType.DEFAULT): ({
            "kind": "Job",
            "metadata": {
                "name": "updated-test-job"
            }
        }, 200),
        ("get", ResponseType.DEFAULT): ([{
            "kind": "Job",
            "metadata": {
                "name": "test-job"
            }
        }], 200),
        ("get", ResponseType.SELECTIVE_LIST): ({
            "kind": "Job",
            "metadata": {
                "name": "test-job"
            }
        }, 200),
        ("post", ResponseType.NO_NAMESPACE): ({
            "kind": "Cluster",
            "metadata": {
                "name": "test-cluster"
            }
        }, 200),
        ("delete", ResponseType.DEFAULT): ({
            "kind": "Job",
            "metadata": {
                "name": "test-job"
            }
        }, 200),
    }

    def mock_request(method: str, url: str, *args: Any,
                     **kwargs: Any) -> MockResponse:
        key_suffix = ResponseType.DEFAULT
        if "server-error" in url:
            key_suffix = ResponseType.SERVER_ERROR
        elif "timeout" in url:
            key_suffix = ResponseType.TIMEOUT
        elif "bad" in url:
            key_suffix = ResponseType.BAD
        elif "error" in url:
            key_suffix = ResponseType.ERROR
        elif "namespace" not in url:
            key_suffix = ResponseType.NO_NAMESPACE
        elif method == "get" and "test-job" in url:
            key_suffix = ResponseType.SELECTIVE_LIST

        key = (method, key_suffix)
        response_data, status_code = response_map.get(
            key, ({
                "unexpected": "response"
            }, 200))

        if key_suffix == ResponseType.TIMEOUT:
            raise requests.exceptions.Timeout("The request timed out")

        return MockResponse(response_data, status_code)

    for method in ["post", "get", "put", "delete"]:
        monkeypatch.setattr(requests,
                            method,
                            lambda url, *args, method=method, **kwargs:
                            mock_request(method, url, *args, **kwargs))


@pytest.fixture
def mock_timeout(monkeypatch: Any) -> None:
    """Fixture to simulate a timeout exception for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> None:
        raise requests.exceptions.Timeout("The request timed out")

    monkeypatch.setattr(requests, "post", mock_post)


@pytest.fixture
def mock_wrong_response(monkeypatch: Any) -> None:
    """Fixture to simulate a wrong response structure for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> MockResponse:
        return MockResponse({"unexpected": "data"}, status_code=200)

    monkeypatch.setattr(requests, "post", mock_post)


@pytest.fixture
def mock_server_error(monkeypatch: Any) -> None:
    """Fixture to simulate server errors (5XX) for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> MockResponse:
        return MockResponse(None, status_code=500)

    monkeypatch.setattr(requests, "post", mock_post)


@pytest.fixture
def mock_bad_request(monkeypatch: Any) -> None:
    """Fixture to simulate a bad request response (400) for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> MockResponse:
        return MockResponse({"detail": "Bad request"}, status_code=400)

    monkeypatch.setattr(requests, "post", mock_post)


@pytest.fixture
def mock_no_json_response(monkeypatch: Any) -> None:
    """Fixture to simulate a response without JSON data (e.g., status 204 No Content) for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> MockResponse:
        return MockResponse(None, status_code=204)  # No Content

    monkeypatch.setattr(requests, "post", mock_post)


def test_namespace_object_api_create_success(namespace_api: NamespaceObjectAPI,
                                             mock_requests: Any) -> None:
    """Tests successful object creation using NamespaceObjectAPI."""
    valid_config = {"kind": "Job", "metadata": {"name": "test-job"}}
    response = namespace_api.create(valid_config)
    assert response.kind == "Job" and response.metadata.name == "test-job"


def test_namespace_object_api_create_api_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests API exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/error"
    with pytest.raises(APIException):
        namespace_api.create({"key": "value"})


def test_namespace_object_api_create_timeout(namespace_api: NamespaceObjectAPI,
                                             mock_timeout: Any) -> None:
    """Tests timeout exception handling during object creation with NamespaceObjectAPI."""
    with pytest.raises(Timeout):
        namespace_api.create({"key": "value"})


def test_namespace_object_api_create_wrong_response(
        namespace_api: NamespaceObjectAPI, mock_wrong_response: Any) -> None:
    """Tests handling of an unexpected response structure from NamespaceObjectAPI."""
    with pytest.raises(ValueError):
        namespace_api.create({"key": "value"})


def test_namespace_object_api_create_server_error(
        namespace_api: NamespaceObjectAPI, mock_server_error: Any) -> None:
    """Tests server error handling during object creation with NamespaceObjectAPI."""
    with pytest.raises(APIException) as exc_info:
        namespace_api.create({"key": "value"})
    assert "500" in str(exc_info.value)


def test_namespace_object_api_create_bad_request(
        namespace_api: NamespaceObjectAPI, mock_bad_request: Any) -> None:
    """Tests bad request error handling during object creation with NamespaceObjectAPI."""
    with pytest.raises(APIException) as exc_info:
        namespace_api.create({"key": "value"})
    assert "Bad request" in str(exc_info.value)


def test_namespace_object_api_create_no_content_response(
        namespace_api: NamespaceObjectAPI, mock_no_json_response: Any) -> None:
    """Tests handling of no content response from NamespaceObjectAPI."""
    with pytest.raises(ValueError):
        namespace_api.create({"key": "value"})


def test_namespace_object_api_update_success(namespace_api: NamespaceObjectAPI,
                                             mock_requests: Any) -> None:
    """Tests successful object update using NamespaceObjectAPI."""
    updated_config = {"kind": "Job", "metadata": {"name": "updated-test-job"}}
    response = namespace_api.update(updated_config)
    assert response.kind == "Job" and response.metadata.name == "updated-test-job"


def test_namespace_object_api_list_success(namespace_api: NamespaceObjectAPI,
                                           mock_requests: Any) -> None:
    """Tests successful object listing using NamespaceObjectAPI."""
    response = namespace_api.list()
    assert isinstance(response, list) and len(response) > 0


def test_namespace_object_api_get_success(namespace_api: NamespaceObjectAPI,
                                          mock_requests: Any) -> None:
    """Tests successful object retrieval using NamespaceObjectAPI."""
    response = namespace_api.get("test-job")
    assert response.kind == "Job" and response.metadata.name == "test-job"


def test_namespace_object_api_delete_success(namespace_api: NamespaceObjectAPI,
                                             mock_requests: Any) -> None:
    """Tests successful object deletion using NamespaceObjectAPI."""
    response = namespace_api.delete("test-job")
    assert response.kind == "Job" and response.metadata.name == "test-job"


def test_namespace_object_api_watch(namespace_api: NamespaceObjectAPI,
                                    monkeypatch: Any) -> None:
    """Tests the watch functionality of NamespaceObjectAPI."""

    def mock_watch_events(
            url: str,
            headers: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        yield {"kind": "Job", "metadata": {"name": "watched-test-job"}}

    monkeypatch.setattr("skyflow.api_client.object_api.watch_events",
                        mock_watch_events)

    for response in namespace_api.watch():
        assert response.kind == "Job" and response.metadata.name == "watched-test-job"
        break


def test_no_namespace_object_api_create_success(
        nonamespace_api: NoNamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object creation using NoNamespaceObjectAPI."""
    valid_config = {"kind": "Cluster", "metadata": {"name": "test-cluster"}}
    response = nonamespace_api.create(valid_config)
    assert response.kind == "Cluster" and response.metadata.name == "test-cluster"
