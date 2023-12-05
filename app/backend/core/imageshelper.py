import base64
import os
from typing import Optional

from azure.storage.blob.aio import ContainerClient

from approaches.approach import Document


async def download_blob_as_base64(blob_container_client: ContainerClient, file_path: str) -> Optional[str]:
    base_name, _ = os.path.splitext(file_path)
    blob = await blob_container_client.get_blob_client(base_name + ".png").download_blob()

    if not blob.properties or not blob.properties.has_key("content_settings"):
        return None
    return base64.b64encode(await blob.readall()).decode("utf-8")


async def fetch_image(blob_container_client: ContainerClient, result: Document) -> Optional[str]:
    if result.sourcepage:
        return await download_blob_as_base64(blob_container_client, result.sourcepage)
    return None
