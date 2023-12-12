from collections import namedtuple

from azure.core.credentials_async import AsyncTokenCredential
from azure.storage.blob import BlobProperties

MockToken = namedtuple("MockToken", ["token", "expires_on", "value"])


class MockAzureCredential(AsyncTokenCredential):
    async def get_token(self, uri):
        return MockToken("", 9999999999, "")


class MockBlobClient:
    async def download_blob(self):
        return MockBlob()


class MockBlob:
    def __init__(self):
        self.properties = BlobProperties(
            name="Financial Market Analysis Report 2023-7.png", content_settings={"content_type": "image/png"}
        )

    async def readall(self):
        return b"\x89PNG\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\x0d\x49\x48\x44\x52\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x00\x37\x6e\xf9\x24\x00\x00\x00\x0a\x49\x44\x41\x54\x78\x9c\x63\x00\x01\x00\x00\x05\x00\x01\x0d\x0d\x2d\xba\x1b\x00\x00\x00\x00\x49\x45\x4e\x44\xae\x42\x60\x82"


class MockKeyVaultSecret:
    def __init__(self, value):
        self.value = value


class MockKeyVaultSecretClient:
    async def get_secret(self, secret_name):
        return MockKeyVaultSecret("mysecret")
