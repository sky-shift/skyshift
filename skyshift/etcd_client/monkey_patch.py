"""
Monkey patches etcd3 package to better support SkyShift.
"""
import etcd3
import etcd3.utils as utils


# Hack: ETCD3 does not return the deleted values, so we monkey patch it.
@etcd3.MultiEndpointEtcd3Client._handle_errors  # pylint: disable=protected-access
def delete_prefix(self, prefix, prev_kv=False):
    """Delete a range of keys with a prefix in etcd."""
    delete_request = self._build_delete_request(  # pylint: disable=protected-access
        prefix,
        range_end=utils.prefix_range_end(utils.to_bytes(prefix)),
        prev_kv=prev_kv,
    )
    return self.kvstub.DeleteRange(delete_request,
                                   self.timeout,
                                   credentials=self.call_credentials,
                                   metadata=self.metadata)
