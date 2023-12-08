import datetime
import io
import os
import re
from typing import List, Optional, Union

import fitz  # type: ignore
from azure.core.credentials_async import AsyncTokenCredential
from azure.storage.blob import BlobSasPermissions, UserDelegationKey, generate_blob_sas, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from .listfilestrategy import File


class BlobManager:
    """
    Class to manage uploading and deleting blobs containing citation information from a blob storage account
    """

    def __init__(
        self,
        endpoint: str,
        container: str,
        credential: Union[AsyncTokenCredential, str],
        store_page_images: bool = False,
        verbose: bool = False,
    ):
        self.endpoint = endpoint
        self.credential = credential
        self.container = container
        self.store_page_images = store_page_images
        self.verbose = verbose
        self.user_delegation_key: Optional[UserDelegationKey] = None

    async def upload_blob(self, file: File) -> Optional[List[str]]:
        async with BlobServiceClient(
            account_url=self.endpoint, credential=self.credential
        ) as service_client, service_client.get_container_client(self.container) as container_client:
            if not await container_client.exists():
                await container_client.create_container()

            # Re-open and upload the original file
            with open(file.content.name, "rb") as reopened_file:
                blob_name = BlobManager.blob_name_from_file_name(file.content.name)
                print(f"\tUploading blob for whole file -> {blob_name}")
                await container_client.upload_blob(blob_name, reopened_file, overwrite=True)

            if self.store_page_images and os.path.splitext(file.content.name)[1].lower() == ".pdf":
                return await self.upload_pdf_blob_images(service_client, container_client, file)

        return None

    async def get_blob_sas_365days(self):
        async with BlobServiceClient(account_url=self.endpoint, credential=self.credential) as service_client:
            delegation_key_start_time = datetime.datetime.now(datetime.timezone.utc)
            delegation_key_start_time -= datetime.timedelta(minutes=10)
            delegation_key_expiry_time = delegation_key_start_time + datetime.timedelta(days=7)
            user_delegation_key = await service_client.get_user_delegation_key(
                delegation_key_start_time, delegation_key_expiry_time
            )
            if service_client.account_name is not None:
                sas_token = generate_container_sas(
                    account_name=service_client.account_name,
                    container_name=self.container,
                    user_delegation_key=user_delegation_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=delegation_key_expiry_time,
                    start=delegation_key_start_time,
                )
                print(sas_token)
                print(service_client.url)
            return f"ContainerSharedAccessUri=https://stl5kzdk2in3t4w.blob.core.windows.net/content?sp=rl&st=2023-12-07T02:43:43Z&se=2023-12-07T10:43:43Z&skoid=0a6c3b2c-cf52-4d0c-a5f7-f51d31b71004&sktid=72f988bf-86f1-41af-91ab-2d7cd011db47&skt=2023-12-07T02:43:43Z&ske=2023-12-07T10:43:43Z&sks=b&skv=2022-11-02&spr=https&sv=2022-11-02&sr=c&sig=qkezDEz%2B9OrxJoH%2Frce33PUgJpZSkfzS4yQDAweZUp8%3D"

    async def upload_pdf_blob_images(
        self, service_client: BlobServiceClient, container_client: ContainerClient, file: File
    ) -> List[str]:
        with open(file.content.name, "rb") as reopened_file:
            reader = PdfReader(reopened_file)
            page_count = len(reader.pages)
        doc = fitz.open(file.content.name)
        sas_uris = []
        start_time = datetime.datetime.now(datetime.timezone.utc)
        expiry_time = start_time + datetime.timedelta(days=1)

        for i in range(page_count):
            blob_name = BlobManager.blob_image_name_from_file_page(file.content.name, i)
            if self.verbose:
                print(f"\tConverting page {i} to image and uploading -> {blob_name}")

            doc = fitz.open(file.content.name)
            page = doc.load_page(i)
            pix = page.get_pixmap()
            original_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # type: ignore

            # Create a new image with additional space for text
            text_height = 40  # Height of the text area
            new_img = Image.new("RGB", (original_img.width, original_img.height + text_height), "white")

            # Paste the original image onto the new image
            new_img.paste(original_img, (0, text_height))

            # Draw the text on the white area
            font = ImageFont.truetype("arial.ttf", 20)
            draw = ImageDraw.Draw(new_img)
            text = f"SourceFileName:{blob_name}"

            # 10 pixels from the top and left of the image
            x = 10
            y = 10
            draw.text((x, y), text, font=font, fill="black")

            output = io.BytesIO()
            new_img.save(output, format="PNG")
            output.seek(0)

            blob_client = await container_client.upload_blob(blob_name, output, overwrite=True)
            if not self.user_delegation_key:
                self.user_delegation_key = await service_client.get_user_delegation_key(start_time, expiry_time)

            if blob_client.account_name is not None:
                sas_token = generate_blob_sas(
                    account_name=blob_client.account_name,
                    container_name=blob_client.container_name,
                    blob_name=blob_client.blob_name,
                    user_delegation_key=self.user_delegation_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=expiry_time,
                    start=start_time,
                )
                sas_uris.append(f"{blob_client.url}?{sas_token}")

        return sas_uris

    async def remove_blob(self, path: Optional[str] = None):
        async with BlobServiceClient(
            account_url=self.endpoint, credential=self.credential
        ) as service_client, service_client.get_container_client(self.container) as container_client:
            if not await container_client.exists():
                return
            if path is None:
                prefix = None
                blobs = container_client.list_blob_names()
            else:
                prefix = os.path.splitext(os.path.basename(path))[0]
                blobs = container_client.list_blob_names(name_starts_with=os.path.splitext(os.path.basename(prefix))[0])
            async for blob_path in blobs:
                # This still supports PDFs split into individual pages, but we could remove in future to simplify code
                if (
                    prefix is not None
                    and (
                        not re.match(rf"{prefix}-\d+\.pdf", blob_path) or not re.match(rf"{prefix}-\d+\.png", blob_path)
                    )
                ) or (path is not None and blob_path == os.path.basename(path)):
                    continue
                if self.verbose:
                    print(f"\tRemoving blob {blob_path}")
                await container_client.delete_blob(blob_path)

    @classmethod
    def sourcepage_from_file_page(cls, filename, page=0) -> str:
        if os.path.splitext(filename)[1].lower() == ".pdf":
            return f"{os.path.basename(filename)}#page={page+1}"
        else:
            return os.path.basename(filename)

    @classmethod
    def blob_image_name_from_file_page(cls, filename, page=0) -> str:
        return os.path.splitext(os.path.basename(filename))[0] + f"-{page}" + ".png"

    @classmethod
    def blob_name_from_file_name(cls, filename) -> str:
        return os.path.basename(filename)
