"""
Monkey patches etcd3 package to better support Skyflow.
"""
import etcd3
from etcd3.client import _handle_errors


# Hack: ETCD3 does not return the deleted values, so we monkey patch it.
@_handle_errors
def delete_prefix(self, prefix, prev_kv=False):
    """Delete a range of keys with a prefix in etcd."""
    delete_request = self._build_delete_request(  # pylint: disable=protected-access
        prefix,
        range_end=etcd3.utils.increment_last_byte(
            etcd3.utils.to_bytes(prefix)),
        prev_kv=prev_kv,
    )
    delete_response = self.kvstub.DeleteRange(
        delete_request,
        self.timeout,
        credentials=self.call_credentials,
        metadata=self.metadata,
    )
    return delete_response
