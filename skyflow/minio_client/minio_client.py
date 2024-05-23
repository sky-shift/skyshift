import json
import traceback
from minio import Minio
from minio.error import S3Error

class MinIOClient:
    """MinIO client for managing objects in an S3-compatible store."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool = False):
        """
        Initializes the MinIO Client. Optional enable https.
        """
        self.client = Minio(endpoint, access_key, secret_key, secure=secure)

    def ensure_bucket_exists(self, bucket_name: str):
        """
        Ensure the bucket exists.
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
        except S3Error as e:
            print(f"Error creating bucket: {e}")

    def write(self, bucket_name: str, object_name: str, data):
        """
        Write data to an object.
        """
        try:
            json_data = json.dumps(data)
            self.client.put_object(bucket_name, object_name, data=json_data.encode('utf-8'), length=len(json_data))
        except S3Error as e:
            print(traceback.format_exc())
            raise e

    def read(self, bucket_name: str, object_name: str):
        """
        Read data from an object.
        """
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            return json.loads(data.decode('utf-8'))
        except S3Error as e:
            print(traceback.format_exc())
            raise e

    def delete(self, bucket_name: str, object_name: str):
        """
        Delete an object.
        """
        try:
            self.client.remove_object(bucket_name, object_name)
        except S3Error as e:
            print(traceback.format_exc())
            raise e
