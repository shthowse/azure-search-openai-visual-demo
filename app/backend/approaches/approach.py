from dataclasses import dataclass
from typing import Any, AsyncGenerator, List, Optional, Union, cast

import aiohttp
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import (
    CaptionResult,
    QueryType,
    RawVectorQuery,
    VectorQuery,
)
from openai import AsyncOpenAI
from quart import current_app

from core.authentication import AuthenticationHelper


@dataclass
class Document:
    id: Optional[str]
    content: Optional[str]
    embedding: Optional[List[float]]
    image_embedding: Optional[List[float]]
    category: Optional[str]
    sourcepage: Optional[str]
    sourcefile: Optional[str]
    oids: Optional[List[str]]
    groups: Optional[List[str]]
    captions: List[CaptionResult]

    def serialize_for_results(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "embedding": Document.trim_embeddings(self.embedding),
            "imageEmbedding": Document.trim_embeddings(self.image_embedding),
            "category": self.category,
            "sourcepage": self.sourcepage,
            "sourcefile": self.sourcefile,
            "oids": self.oids,
            "groups": self.groups,
            "captions": [
                {
                    "additional_properties": caption.additional_properties,
                    "text": caption.text,
                    "highlights": caption.highlights,
                }
                for caption in self.captions
            ]
            if self.captions
            else [],
        }

    @classmethod
    def trim_embeddings(cls, embedding: Optional[List[float]]) -> Optional[str]:
        if embedding:
            if len(embedding) > 2:
                # Format the embedding list to show the first 2 items followed by the count of the remaining items."""
                return f"[{embedding[0]}, {embedding[1]} ...+{len(embedding) - 2} more]"
            else:
                return str(embedding)

        return None


@dataclass
class ThoughtStep:
    title: str
    description: Optional[Any]
    props: Optional[dict[str, Any]] = None


class Approach:
    def __init__(
        self,
        search_client: SearchClient,
        openai_client: AsyncOpenAI,
        query_language: Optional[str],
        query_speller: Optional[str],
        embedding_deployment: Optional[str],  # Not needed for non-Azure OpenAI or for retrieval_mode="text"
        embedding_model: str,
        openai_host: str,
    ):
        self.search_client = search_client
        self.openai_client = openai_client
        self.query_language = query_language
        self.query_speller = query_speller
        self.embedding_deployment = embedding_deployment
        self.embedding_model = embedding_model
        self.openai_host = openai_host

    def build_filter(self, overrides: dict[str, Any], auth_claims: dict[str, Any]) -> Optional[str]:
        exclude_category = overrides.get("exclude_category") or None
        security_filter = AuthenticationHelper.build_security_filters(overrides, auth_claims)
        filters = []
        if exclude_category:
            filters.append("category ne '{}'".format(exclude_category.replace("'", "''")))
        if security_filter:
            filters.append(security_filter)
        return None if len(filters) == 0 else " and ".join(filters)

    async def search(
        self,
        top: int,
        query_text: Optional[str],
        filter: Optional[str],
        vectors: List[VectorQuery],
        use_semantic_ranker: bool,
        use_semantic_captions: bool,
    ) -> List[Document]:
        # Use semantic ranker if requested and if retrieval mode is text or hybrid (vectors + text)
        if use_semantic_ranker and query_text:
            results = await self.search_client.search(
                search_text=query_text,
                filter=filter,
                query_type=QueryType.SEMANTIC,
                query_language=self.query_language,
                query_speller=self.query_speller,
                semantic_configuration_name="default",
                top=top,
                query_caption="extractive|highlight-false" if use_semantic_captions else None,
                vector_queries=vectors,
            )
        else:
            results = await self.search_client.search(
                search_text=query_text or "", filter=filter, top=top, vectors=vectors
            )

        documents = []
        async for page in results.by_page():
            async for document in page:
                documents.append(
                    Document(
                        id=document.get("id"),
                        content=document.get("content"),
                        embedding=document.get("embedding"),
                        image_embedding=document.get("imageEmbedding"),
                        category=document.get("category"),
                        sourcepage=document.get("sourcepage"),
                        sourcefile=document.get("sourcefile"),
                        oids=document.get("oids"),
                        groups=document.get("groups"),
                        captions=cast(List[CaptionResult], document.get("@search.captions")),
                    )
                )
        return documents

    async def compute_text_embedding(self, q: str):
        embedding = await self.openai_client.embeddings.create(
            # Azure Open AI takes the deployment name as the model name
            model=self.embedding_deployment if self.embedding_deployment else self.embedding_model,
            input=q,
        )
        query_vector = embedding.data[0].embedding
        return RawVectorQuery(vector=query_vector, k=50, fields="embedding")

    async def compute_image_embedding(self, q: str):
        endpoint = f"{current_app.config['vision_endpoint']}computervision/retrieval:vectorizeText"
        params = {"api-version": "2023-02-01-preview", "modelVersion": "latest"}
        headers = {"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": current_app.config["vision_key"]}
        data = {"text": q}

        async with aiohttp.ClientSession() as session:
            async with session.post(url=endpoint, params=params, headers=headers, json=data) as response:
                response.raise_for_status()
                json = await response.json()
                image_query_vector = json["vector"]
        return RawVectorQuery(vector=image_query_vector, k=50, fields="imageEmbedding")

    async def run(
        self, messages: list[dict], stream: bool = False, session_state: Any = None, context: dict[str, Any] = {}
    ) -> Union[dict[str, Any], AsyncGenerator[dict[str, Any], None]]:
        raise NotImplementedError
