"""
Unit tests for the API client module specific to scheduler.

To run the tests, use the following command:
pytest skyshift/tests/api_client_scheduler_unit_tests.py

To run one specific test, use the following command:
pytest skyshift/tests/api_client_scheduler_unit_tests.py::test_namespace_object_api_create_success

"""
from enum import Enum
from typing import Any, Dict, List, Tuple, Union

import pytest
import requests

from skyshift.api_client.object_api import (NamespaceObjectAPI,
                                           NoNamespaceObjectAPI)

# pylint: disable=W0613 (unused-argument)

# Test Cases
DEFAULT_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "name":
                "updated-filter-1",
                "match_labels": {
                    "purpose": "dev"
                },
                "match_expressions": [{
                    "key": "location",
                    "operator": "NotIn",
                    "values": ["eu"]
                }]
            }, {
                "name":
                "updated-filter-2",
                "match_labels": {
                    "purpose": "staging"
                },
                "match_expressions": [{
                    "key": "location",
                    "operator": "NotIn",
                    "values": ["eu", "ap"]
                }]
            }],
            "preferences": [
                {
                    "name": "updated-pref-1",
                    "match_labels": {
                        "sky-cluster-name": "mycluster-dev-1"
                    },
                    "weight": 100
                },
                {
                    "name":
                    "updated-pref-2",
                    "match_labels": {
                        "purpose": "dev"
                    },
                    "match_expressions": [{
                        "key": "location",
                        "operator": "In",
                        "values": ["na"]
                    }],
                    "weight":
                    50
                },
                {
                    "name": "updated-pref-3",
                    "match_labels": {
                        "purpose": "dev"
                    },
                    "weight": 25
                },
            ]
        }
    }
}

MATCH_EXPRESSIONS_OR_LABELS_ONLY_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "name":
                "filter-1",
                "match_expressions": [{
                    "key": "location",
                    "operator": "NotIn",
                    "values": ["eu"]
                }]
            }, {
                "name": "filter-2",
                "match_labels": {
                    "purpose": "staging"
                },
            }],
            "preferences": [
                {
                    "name": "pref-1",
                    "match_labels": {
                        "sky-cluster-name": "mycluster-dev-1"
                    },
                    "weight": 100
                },
                {
                    "name":
                    "pref-2",
                    "match_expressions": [{
                        "key": "location",
                        "operator": "In",
                        "values": ["na"]
                    }],
                    "weight":
                    50
                },
                {
                    "name": "pref-3",
                    "match_labels": {
                        "purpose": "dev"
                    },
                    "weight": 25
                },
            ]
        }
    }
}

FILTER_EMPTY_NAME_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "match_labels": {
                    "purpose": "dev"
                }
            }]
        }
    }
}

FILTER_NAME_SYNTAX_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "name": "updated_filter_1",
                "match_labels": {
                    "purpose": "dev"
                }
            }]
        }
    }
}

FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "name": "updated-filter-1",
                "match_labels": {}
            }]
        }
    }
}

FILTER_EMPTY_MATCH_LABELS_KEY_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "name": "updated-filter-1",
                "match_labels": {
                    "": "dev"
                }
            }]
        }
    }
}

PREFERENCE_EMPTY_NAME_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "match_labels": {
                    "sky-cluster-name": "mycluster-dev-1"
                },
                "weight": 100
            }]
        }
    }
}

PREFERENCE_NAME_SYNTAX_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated_preference_1",
                "match_labels": {
                    "sky-cluster-name": "mycluster-dev-1"
                },
                "weight": 100
            }]
        }
    }
}

PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated-preference-1",
                "match_labels": {},
                "weight": 100
            }]
        }
    }
}

PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated-preference-1",
                "match_labels": {
                    "": "mycluster-dev-1"
                },
                "weight": 100
            }]
        }
    }
}

WEIGHT_STR_TYPE_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated-pref-1",
                "match_labels": {
                    "sky-cluster-name": "mycluster-dev-1"
                },
                "weight": "ten"
            }]
        }
    }
}

WEIGHT_FLOAT_TYPE_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated-pref-1",
                "match_labels": {
                    "sky-cluster-name": "mycluster-dev-1"
                },
                "weight": 99.9
            }]
        }
    }
}

WEIGHT_VALUE_RANGE_LOW_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated-pref-1",
                "match_labels": {
                    "sky-cluster-name": "mycluster-dev-1"
                },
                "weight": 0
            }]
        }
    }
}

WEIGHT_VALUE_RANGE_HIGH_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name": "updated-pref-1",
                "match_labels": {
                    "sky-cluster-name": "mycluster-dev-1"
                },
                "weight": 101
            }]
        }
    }
}

FILTER_DUP_NAME_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "filters": [{
                "name": "filter-dup-name",
                "match_labels": {
                    "purpose": "dev"
                }
            }, {
                "name": "filter-dup-name",
                "match_labels": {
                    "purpose": "staging"
                },
            }]
        }
    }
}

PREFERENCE_DUP_NAME_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [
                {
                    "name": "updated-pref-dup-name",
                    "match_labels": {
                        "sky-cluster-name": "mycluster-dev-1"
                    },
                    "weight": 100
                },
                {
                    "name": "updated-pref-dup-name",
                    "match_labels": {
                        "purpose": "dev"
                    },
                    "weight": 25
                },
            ]
        }
    }
}

INVALID_EXPRESSION_OPERATOR_ERROR_JSON = {
    "kind": "Job",
    "metadata": {
        "name": "updated-test-job"
    },
    "spec": {
        "placement": {
            "preferences": [{
                "name":
                "updated-pref-2",
                "match_labels": {
                    "purpose": "dev"
                },
                "match_expressions": [{
                    "key": "location",
                    "operator": "",
                    "values": ["na"]
                }],
                "weight":
                50
            }]
        }
    }
}


class ResponseType(Enum):
    """Possible responses."""

    FILTER_EMPTY_NAME_ERROR = "filter-empty-name-error"
    PREFERENCE_EMPTY_NAME_ERROR = "preference-empty-name-error"
    FILTER_NAME_SYNTAX_ERROR = "filter-syntax-name-error"
    PREFERENCE_NAME_SYNTAX_ERROR = "preference-syntax-name-error"
    FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR = "filter-empty-match-labels-stanza-error"
    FILTER_EMPTY_MATCH_LABELS_KEY_ERROR = "filter-empty-match-labels-key-error"
    PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR = "preference-empty-match-labels-stanza-error"
    PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR = "preference-empty-match-labels-key-error"
    WEIGHT_STR_TYPE_ERROR = "weight-string-type-error"
    WEIGHT_FLOAT_TYPE_ERROR = "weight-float-type-error"
    WEIGHT_VALUE_RANGE_LOW_ERROR = "weight-value-range-low-error"
    WEIGHT_VALUE_RANGE_HIGH_ERROR = "weight-value-range-high-error"
    FILTER_DUP_NAME_ERROR = "filter-dup-name-error"
    PREFERENCE_DUP_NAME_ERROR = "preference-dup-name-error"
    INVALID_EXPRESSION_OPERATOR_ERROR = "invalid-expression-operator-error"
    MATCH_EXPRESSIONS_OR_LABELS_ONLY = "match-expressions-or-labels-only"
    DEFAULT = "default"
    NO_NAMESPACE = "no-namespace"
    SELECTIVE_LIST = "selective-list"


# pylint: disable=R0903 (too-few-public-methods)
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


@pytest.fixture(name="namespace_api")
def fixture_namespace_api() -> NamespaceObjectAPI:
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


@pytest.fixture(name="mock_requests")
def fixture_mock_requests(monkeypatch: Any) -> None:
    """Fixture to mock HTTP requests using a predefined response map."""

    response_map: Dict[Tuple[str, ResponseType], Any] = {
        ("put", ResponseType.FILTER_EMPTY_NAME_ERROR):
        (FILTER_EMPTY_NAME_ERROR_JSON, 200),
        ("put", ResponseType.PREFERENCE_EMPTY_NAME_ERROR):
        (PREFERENCE_EMPTY_NAME_ERROR_JSON, 200),
        ("put", ResponseType.FILTER_NAME_SYNTAX_ERROR):
        (FILTER_NAME_SYNTAX_ERROR_JSON, 200),
        ("put", ResponseType.PREFERENCE_NAME_SYNTAX_ERROR):
        (PREFERENCE_NAME_SYNTAX_ERROR_JSON, 200),
        ("put", ResponseType.FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR):
        (FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR_JSON, 200),
        ("put", ResponseType.FILTER_EMPTY_MATCH_LABELS_KEY_ERROR):
        (FILTER_EMPTY_MATCH_LABELS_KEY_ERROR_JSON, 200),
        ("put", ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR):
        (PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR_JSON, 200),
        ("put", ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR):
        (PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR_JSON, 200),
        ("put", ResponseType.WEIGHT_STR_TYPE_ERROR):
        (WEIGHT_STR_TYPE_ERROR_JSON, 200),
        ("put", ResponseType.WEIGHT_FLOAT_TYPE_ERROR):
        (WEIGHT_FLOAT_TYPE_ERROR_JSON, 200),
        ("put", ResponseType.WEIGHT_VALUE_RANGE_LOW_ERROR):
        (WEIGHT_VALUE_RANGE_LOW_ERROR_JSON, 200),
        ("put", ResponseType.WEIGHT_VALUE_RANGE_HIGH_ERROR):
        (WEIGHT_VALUE_RANGE_HIGH_ERROR_JSON, 200),
        ("put", ResponseType.FILTER_DUP_NAME_ERROR):
        (FILTER_DUP_NAME_ERROR_JSON, 200),
        ("put", ResponseType.PREFERENCE_DUP_NAME_ERROR):
        (PREFERENCE_DUP_NAME_ERROR_JSON, 200),
        ("put", ResponseType.INVALID_EXPRESSION_OPERATOR_ERROR):
        (INVALID_EXPRESSION_OPERATOR_ERROR_JSON, 200),
        ("put", ResponseType.MATCH_EXPRESSIONS_OR_LABELS_ONLY):
        (MATCH_EXPRESSIONS_OR_LABELS_ONLY_JSON, 200),
        ("put", ResponseType.DEFAULT): (DEFAULT_JSON, 200),
    }

    # pylint: disable=R0912 (too-many-branches)
    def mock_request(method: str, url: str, *args: Any,
                     **kwargs: Any) -> MockResponse:
        key_suffix = ResponseType.DEFAULT
        if ResponseType.FILTER_EMPTY_NAME_ERROR.value in url:
            key_suffix = ResponseType.FILTER_EMPTY_NAME_ERROR
        elif ResponseType.PREFERENCE_EMPTY_NAME_ERROR.value in url:
            key_suffix = ResponseType.PREFERENCE_EMPTY_NAME_ERROR
        elif ResponseType.FILTER_NAME_SYNTAX_ERROR.value in url:
            key_suffix = ResponseType.FILTER_NAME_SYNTAX_ERROR
        elif ResponseType.PREFERENCE_NAME_SYNTAX_ERROR.value in url:
            key_suffix = ResponseType.PREFERENCE_NAME_SYNTAX_ERROR
        elif ResponseType.FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR.value in url:
            key_suffix = ResponseType.FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR
        elif ResponseType.FILTER_EMPTY_MATCH_LABELS_KEY_ERROR.value in url:
            key_suffix = ResponseType.FILTER_EMPTY_MATCH_LABELS_KEY_ERROR
        elif ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR.value in url:
            key_suffix = ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR
        elif ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR.value in url:
            key_suffix = ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR
        elif ResponseType.WEIGHT_STR_TYPE_ERROR.value in url:
            key_suffix = ResponseType.WEIGHT_STR_TYPE_ERROR
        elif ResponseType.WEIGHT_FLOAT_TYPE_ERROR.value in url:
            key_suffix = ResponseType.WEIGHT_FLOAT_TYPE_ERROR
        elif ResponseType.WEIGHT_VALUE_RANGE_LOW_ERROR.value in url:
            key_suffix = ResponseType.WEIGHT_VALUE_RANGE_LOW_ERROR
        elif ResponseType.FILTER_DUP_NAME_ERROR.value in url:
            key_suffix = ResponseType.FILTER_DUP_NAME_ERROR
        elif ResponseType.PREFERENCE_DUP_NAME_ERROR.value in url:
            key_suffix = ResponseType.PREFERENCE_DUP_NAME_ERROR
        elif ResponseType.INVALID_EXPRESSION_OPERATOR_ERROR.value in url:
            key_suffix = ResponseType.INVALID_EXPRESSION_OPERATOR_ERROR
        elif ResponseType.MATCH_EXPRESSIONS_OR_LABELS_ONLY.value in url:
            key_suffix = ResponseType.MATCH_EXPRESSIONS_OR_LABELS_ONLY

        key = (method, key_suffix)
        response_data, status_code = response_map.get(
            key, ({
                "unexpected": "response"
            }, 200))

        return MockResponse(response_data, status_code)

    for method in ["post", "get", "put", "delete"]:
        monkeypatch.setattr(requests,
                            method,
                            lambda url, *args, method=method, **kwargs:
                            mock_request(method, url, *args, **kwargs))


@pytest.fixture
def mock_wrong_response(monkeypatch: Any) -> None:
    """Fixture to simulate a wrong response structure for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> MockResponse:
        return MockResponse({"unexpected": "data"}, status_code=200)

    monkeypatch.setattr(requests, "post", mock_post)


@pytest.fixture
def mock_no_json_response(monkeypatch: Any) -> None:
    """Fixture to simulate a response without JSON data (e.g., status 204 No Content) for POST requests."""

    def mock_post(*args: Any, **kwargs: Any) -> MockResponse:
        return MockResponse(None, status_code=204)  # No Content

    monkeypatch.setattr(requests, "post", mock_post)


def test_namespace_object_api_update_missing_filter_name_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.FILTER_EMPTY_NAME_ERROR.value
    with pytest.raises(ValueError, match=r".*Object name cannot be empty.*"):
        namespace_api.update(FILTER_EMPTY_NAME_ERROR_JSON)


def test_namespace_object_api_update_filter_name_value_syntax_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.FILTER_NAME_SYNTAX_ERROR.value
    with pytest.raises(ValueError, match=r".*Invalid object name.*"):
        namespace_api.update(FILTER_NAME_SYNTAX_ERROR_JSON)


def test_namespace_object_api_update_empty_filter_match_labels_stanza_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR.value
    with pytest.raises(
            ValueError,
            match=r".*Filter must contain at least one evaluation criteria.*"):
        namespace_api.update(FILTER_EMPTY_MATCH_LABELS_STANZA_ERROR_JSON)


def test_namespace_object_api_update_empty_filter_match_labels_key_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.FILTER_EMPTY_MATCH_LABELS_KEY_ERROR.value
    with pytest.raises(ValueError,
                       match=r".*Labels' keys can not be empty strings.*"):
        namespace_api.update(FILTER_EMPTY_MATCH_LABELS_KEY_ERROR_JSON)


def test_namespace_object_api_update_missing_preference_name_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.PREFERENCE_EMPTY_NAME_ERROR.value
    with pytest.raises(ValueError, match=r".*Object name cannot be empty.*"):
        namespace_api.update(PREFERENCE_EMPTY_NAME_ERROR_JSON)


def test_namespace_object_api_update_missing_preference_name_value_syntax_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.PREFERENCE_NAME_SYNTAX_ERROR.value
    with pytest.raises(ValueError, match=r".*Invalid object name.*"):
        namespace_api.update(PREFERENCE_NAME_SYNTAX_ERROR_JSON)


def test_namespace_object_api_update_empty_preference_match_labels_stanza_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR.value
    with pytest.raises(
            ValueError,
            match=
            r".*Preference must contain at least one evaluation criteria.*"):
        namespace_api.update(PREFERENCE_EMPTY_MATCH_LABELS_STANZA_ERROR_JSON)


def test_namespace_object_api_update_empty_preference_match_labels_key_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR.value
    with pytest.raises(ValueError,
                       match=r".*Labels' keys can not be empty strings.*"):
        namespace_api.update(PREFERENCE_EMPTY_MATCH_LABELS_KEY_ERROR_JSON)


def test_namespace_object_api_update_invalid_weight_type_string_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.WEIGHT_STR_TYPE_ERROR.value
    with pytest.raises(ValueError,
                       match=r".*unable to parse string as an integer.*"):
        namespace_api.update(WEIGHT_STR_TYPE_ERROR_JSON)


def test_namespace_object_api_update_invalid_weight_type_float_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.WEIGHT_FLOAT_TYPE_ERROR.value
    with pytest.raises(
            ValueError,
            match=
            r".*Input should be a valid integer, got a number with a fractional part.*"
    ):
        namespace_api.update(WEIGHT_FLOAT_TYPE_ERROR_JSON)


def test_namespace_object_api_update_weight_out_of_range_low_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.WEIGHT_VALUE_RANGE_LOW_ERROR.value
    with pytest.raises(
            ValueError,
            match=r".*preference `weight` must be within range 1 - 100.*"):
        namespace_api.update(WEIGHT_VALUE_RANGE_LOW_ERROR_JSON)


def test_namespace_object_api_update_weight_out_of_range_high_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.WEIGHT_VALUE_RANGE_LOW_ERROR.value
    with pytest.raises(
            ValueError,
            match=r".*preference `weight` must be within range 1 - 100.*"):
        namespace_api.update(WEIGHT_VALUE_RANGE_HIGH_ERROR_JSON)


def test_namespace_object_api_update_filter_dup_names_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.FILTER_DUP_NAME_ERROR.value
    with pytest.raises(ValueError, match=r".*Duplicate filter `name`.*"):
        namespace_api.update(FILTER_DUP_NAME_ERROR_JSON)


def test_namespace_object_api_update_preference_dup_names_value_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests value exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.PREFERENCE_DUP_NAME_ERROR.value
    with pytest.raises(ValueError, match=r".*Duplicate preference `name`.*"):
        namespace_api.update(PREFERENCE_DUP_NAME_ERROR_JSON)


def test_namespace_object_api_update_invalid_expression_operator_api_exception(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests API exception handling during object creation with NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.INVALID_EXPRESSION_OPERATOR_ERROR.value
    with pytest.raises(ValueError,
                       match=r".*Invalid match expression `operator`.*"):
        namespace_api.update(INVALID_EXPRESSION_OPERATOR_ERROR_JSON)


def test_namespace_object_api_update_match_expressions_or_labels_success(
        namespace_api: NamespaceObjectAPI, mock_requests: Any) -> None:
    """Tests successful object update using NamespaceObjectAPI."""
    namespace_api.url += "/" + ResponseType.MATCH_EXPRESSIONS_OR_LABELS_ONLY.value
    updated_config = MATCH_EXPRESSIONS_OR_LABELS_ONLY_JSON
    response = namespace_api.update(updated_config)
    assert response.kind == "Job" and response.metadata.name == "updated-test-job" and response.spec.placement.filters[
        0].name == "filter-1" and response.spec.placement.filters[
            1].name == "filter-2"


def test_namespace_object_api_update_success(namespace_api: NamespaceObjectAPI,
                                             mock_requests: Any) -> None:
    """Tests successful object update using NamespaceObjectAPI."""
    updated_config = DEFAULT_JSON
    response = namespace_api.update(updated_config)
    assert response.kind == "Job" and response.metadata.name == "updated-test-job" and response.spec.placement.filters[
        0].name == "updated-filter-1" and response.spec.placement.filters[
            1].name == "updated-filter-2"
