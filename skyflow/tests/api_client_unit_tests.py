from typing import Any, Dict, Generator, List, Tuple, Union

import pytest
import requests
from requests import Timeout

from skyflow.api_client.object_api import (APIException, NamespaceObjectAPI,
                                           NoNamespaceObjectAPI)


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

    response_map: Dict[Tuple[str, str], Any] = {
        ("post", "error"): ({"detail": "Error occurred"}, 404),
        ("post", "timeout"): ("timeout", None),
        ("post", "bad"): ({"detail": "Bad request"}, 400),
        ("post", "server-error"): (None, 500),
        ("post", "default"): ({"kind": "Job", "metadata": {"name": "test-job"}}, 200),
        ("put", "default"): ({"kind": "Job", "metadata": {"name": "updated-test-job"}}, 200),
        ("get", "default"): ([{"kind": "Job", "metadata": {"name": "test-job"}}], 200),
        ("get", "selective-list"): ({"kind": "Job", "metadata": {"name": "test-job"}}, 200),
        ("post", "no-namespace"): ({"kind": "Cluster", "metadata": {"name": "test-cluster"}}, 200),
        ("delete", "default"):  ({"kind": "Job", "metadata": {"name": "test-job"}}, 200),
    }

    def mock_request(method: str, url: str, *args: Any, **kwargs: Any) -> MockResponse:
        """Determines the mock response based on the request method and URL."""
        key_suffix = "default"
        if "error" in url:
            key_suffix = "error"
        elif "timeout" in url:
            key_suffix = "timeout"
        elif "bad" in url:
            key_suffix = "bad"
        elif "server-error" in url:
            key_suffix = "server-error"
        elif "namespace" not in url:
            key_suffix = "no-namespace"
        elif method == "get" and "test-job" in url:
            key_suffix = "selective-list"

        key = (method, key_suffix)
        response_data, status_code = response_map.get(key, ({"unexpected": "response"}, 200))

        if key_suffix == "timeout":
            raise requests.exceptions.Timeout("The request timed out")

        return MockResponse(response_data, status_code)

    for method in ["post", "get", "put", "delete"]:
        monkeypatch.setattr(requests, method, lambda url, *args, method=method, **kwargs: mock_request(method, url, *args, **kwargs))

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

def test_namespace_object_api_create_success(namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object creation using NamespaceObjectAPI."""
    valid_config = {"kind": "Job", "metadata": {"name": "test-job"}}
    response = namespace_api.create(valid_config)
    assert response.kind == "Job" and response.metadata.name == "test-job"

def test_namespace_object_api_create_api_exception(namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests API exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/error"
    with pytest.raises(APIException):
        namespace_api.create({"key": "value"})

def test_namespace_object_api_create_timeout(namespace_api: NamespaceObjectAPI, mock_timeout: Any) -> None:
    """Tests timeout exception handling during object creation with NamespaceObjectAPI."""
    with pytest.raises(Timeout):
        namespace_api.create({"key": "value"})

def test_namespace_object_api_create_wrong_response(namespace_api: NamespaceObjectAPI, mock_wrong_response: Any) -> None:
    """Tests handling of an unexpected response structure from NamespaceObjectAPI."""
    with pytest.raises(ValueError):
        namespace_api.create({"key": "value"})

def test_namespace_object_api_create_server_error(namespace_api: NamespaceObjectAPI, mock_server_error: Any) -> None:
    """Tests server error handling during object creation with NamespaceObjectAPI."""
    with pytest.raises(APIException) as exc_info:
        namespace_api.create({"key": "value"})
    assert str(exc_info.value) == "HTTP error occurred: Status code 500"

def test_namespace_object_api_create_bad_request(namespace_api: NamespaceObjectAPI, mock_bad_request: Any) -> None:
    """Tests bad request error handling during object creation with NamespaceObjectAPI."""
    with pytest.raises(APIException) as exc_info:
        namespace_api.create({"key": "value"})
    assert "Bad request" in str(exc_info.value)

def test_namespace_object_api_create_no_content_response(namespace_api: NamespaceObjectAPI, mock_no_json_response: Any) -> None:
    """Tests handling of no content response from NamespaceObjectAPI."""
    with pytest.raises(ValueError):
        namespace_api.create({"key": "value"})

def test_namespace_object_api_update_success(namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object update using NamespaceObjectAPI."""
    updated_config = {"kind": "Job", "metadata": {"name": "updated-test-job"}}
    response = namespace_api.update(updated_config)
    assert response.kind == "Job" and response.metadata.name == "updated-test-job"

def test_namespace_object_api_list_success(namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object listing using NamespaceObjectAPI."""
    response = namespace_api.list()
    assert isinstance(response, list) and len(response) > 0

def test_namespace_object_api_get_success(namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object retrieval using NamespaceObjectAPI."""
    response = namespace_api.get("test-job")
    assert response.kind == "Job" and response.metadata.name == "test-job"

def test_namespace_object_api_delete_success(namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object deletion using NamespaceObjectAPI."""
    response = namespace_api.delete("test-job")
    assert response.kind == "Job" and response.metadata.name == "test-job"

def test_namespace_object_api_watch(namespace_api: NamespaceObjectAPI, monkeypatch: Any) -> None:
    """Tests the watch functionality of NamespaceObjectAPI."""
    def mock_watch_events(url: str) -> Generator[Dict[str, Any], None, None]:
        yield {"kind": "Job", "metadata": {"name": "watched-test-job"}}
    monkeypatch.setattr("skyflow.api_client.object_api.watch_events", mock_watch_events)

    for response in namespace_api.watch():
        assert response.kind == "Job" and response.metadata.name == "watched-test-job"
        break

def test_no_namespace_object_api_create_success(nonamespace_api: NoNamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object creation using NoNamespaceObjectAPI."""
    valid_config = {"kind": "Cluster", "metadata": {"name": "test-cluster"}}
    response = nonamespace_api.create(valid_config)
    assert response.kind == "Cluster" and response.metadata.name == "test-cluster"