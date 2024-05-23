"""
Monkey patches etcd3 package to better support Skyflow.
"""
import asyncio

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


@_handle_errors
async def watch_response(self, key, **kwargs):
    """
    Watch a key asynchronously.
    """
    response_queue = asyncio.Queue()
    cancel_event = asyncio.Event()
    def callback(response):
        print("???")
        asyncio.create_task(response_queue.put(response))
        print("PUT: ", response, response_queue.qsize())

    watch_id = self.add_watch_callback(key, callback, **kwargs)

    def cancel():
        cancel_event.set()
        asyncio.create_task(response_queue.put(None))
        self.cancel_watch(watch_id)

    async def iterator():
        while not cancel_event.is_set():
            print("GETTING RESPONSE", response_queue.qsize())
            response = await response_queue.get()
            print("GET: ", response, response_queue.qsize())
            if response is None:
                cancel_event.set()
            if isinstance(response, Exception):
                cancel_event.set()
                raise response
            if not cancel_event.is_set():
                yield response

    return iterator(), cancel
