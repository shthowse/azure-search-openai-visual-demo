import os

import aiohttp
from quart import current_app
import logging


async def generate_image_embeddings(text):
    endpoint = f"{os.environ['AZURE_COMPUTER_VISION_ENDPOINT']}computervision/retrieval:vectorizeText"
    params = {"api-version": "2023-02-01-preview", "modelVersion": "latest"}
    headers = {"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": current_app.config["vision_key"]}
    data = {"text": text}

    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, params=params, headers=headers, json=data) as response:
            if response.status == 200:
                json = await response.json()
                return json["vector"]
            else:
                logging.error(f"Error: {response.status} - {response.text}")
                return None


def serialize_data(doc):
    for key in ["embedding", "imageEmbedding"]:
        if doc.get(key) is not None:
            doc[key] = trim_embedding(doc[key])

    if captions := doc.get("@search.captions"):
        doc["@search.captions"] = [
            {
                "text": caption.text,
                "highlights": caption.highlights,
                "additional_properties": caption.additional_properties,
            }
            for caption in captions
        ]

    return doc


def trim_embedding(embedding):
    """Format the embedding list to show the first 2 items followed by the count of the remaining items."""
    return f"[{embedding[0]}, {embedding[1]} ...+{len(embedding) - 2} more]" if len(embedding) > 2 else embedding
