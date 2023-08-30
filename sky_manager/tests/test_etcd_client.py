from sky_manager import ETCDClient


# To test, run:
# pytest starburst/sky_manager/tests/test_etcd_client.py::TestETCDClient
class TestETCDClient:

    def test_shallow_key(self):
        test_client = ETCDClient()
        test_client.write('a', 1)
        try:
            assert test_client.read('a') == '1'
        finally:
            test_client.delete_all()

    def test_deep_key(self):
        test_client = ETCDClient()
        test_client.write('a/b/c/d/e/f', 1)
        try:
            assert test_client.read('a/b/c/d/e/f') == '1'
        finally:
            test_client.delete_all()
