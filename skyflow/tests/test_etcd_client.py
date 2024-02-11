"""
Tests for ETCD interface.
"""
from skyflow import ETCDClient


# To test, run:
# pytest skyflow/tests/test_etcd_client.py::TestETCDClient
class TestETCDClient:
    """
    Tests for ETCD interface.
    """
    def test_client_single_key(self): # pylint: disable=no-self-use
        """
        Tests the ETCD client for a single key.
        """
        test_client = ETCDClient()
        test_client.write("a", "1")
        try:
            assert test_client.read("a") == ("a", "1")
        finally:
            test_client.delete("a")
        assert test_client.read("a") is None

    def test_client_prefix_keys(self): # pylint: disable=no-self-use
        """
        Tests the ETCD client for a prefix of keys.
        """
        test_client = ETCDClient()
        test_client.write("a/b", "1")
        test_client.write("a/c", "2")
        try:
            assert test_client.read_prefix("a") == [("a/b", "1"), ("a/c", "2")]
        finally:
            test_client.delete_prefix("a")
        assert not test_client.read_prefix("a")
