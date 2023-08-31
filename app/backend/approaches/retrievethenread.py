import base64
import json
import os
from typing import Any

import aiohttp
import openai
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import QueryType
from azure.storage.blob import ContainerClient

from approaches.approach import ApproachResult, AskApproach, ThoughtStep
from core.messagebuilder import MessageBuilder
from text import nonewlines

# Replace these with your own values, either in environment variables or directly here
AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")


class RetrieveThenReadApproach(AskApproach):
    """
    Simple retrieve-then-read implementation, using the Cognitive Search and OpenAI APIs directly. It first retrieves
    top documents from search, then constructs a prompt with them, and then uses OpenAI to generate an completion
    (answer) with that prompt.
    """

    system_chat_template = (
        "You are an intelligent assistant helping Contoso Inc employees with their healthcare plan questions and employee handbook questions. "
        + "Use 'you' to refer to the individual asking the questions even if they ask with 'I'. "
        + "Answer the following question using only the data provided in the sources below. "
        + "For tabular information return it as an html table. Do not return markdown format. "
        + "Each source has a name followed by colon and the actual information, always include the source name for each fact you use in the response. "
        + "If you cannot answer using the sources below, say you don't know. Use below example to answer"
    )

    # shots/sample conversation
    question = """
'What is the deductible for the employee plan for a visit to Overlake in Bellevue?'

Sources:
info1.txt: deductibles depend on whether you are in-network or out-of-network. In-network deductibles are $500 for employee and $1000 for family. Out-of-network deductibles are $1000 for employee and $2000 for family.
info2.pdf: Overlake is in-network for the employee plan.
info3.pdf: Overlake is the name of the area that includes a park and ride near Bellevue.
info4.pdf: In-network institutions include Overlake, Swedish and others in the region
"""
    answer = "In-network deductibles are $500 for employee and $1000 for family [info1.txt] and Overlake is in-network for the employee plan [info2.pdf][info4.pdf]."

    system_chat_template_gptv = (
        "You are an intelligent assistant helping people analyze housing data and projections, the documents contain text, graphs, tables and images. "
        + "Answer the following question using only the data provided in the sources below. "
        + "For tabular information return it as an html table. Do not return markdown format. "
        + "Each text source has a name followed by colon and the actual information, always include the source name for each fact you use in the response. [filename]"
        + "The text and image source can be the same file name, don't use the image title when citing the image source, only use the file name as mentioned"
        + "Each image source has the file name in the top left corner of the image with coordinates (10,10) pixels and is in the format SourceFileName:<file_name>, always include the file_name in the format [file_name] when a image is used"
        + "If you cannot answer using the sources below, say you don't know. Return just the answer without any input texts"
    )

    def __init__(
        self,
        search_client: SearchClient,
        blob_container_client: ContainerClient,
        openai_deployment: str,
        chatgpt_model: str,
        openai_gptv_deployment: str,
        gptv_model: str,
        embedding_deployment: str,
        sourcepage_field: str,
        content_field: str,
    ):
        self.search_client = search_client
        self.blob_container_client = blob_container_client
        self.openai_deployment = openai_deployment
        self.chatgpt_model = chatgpt_model
        self.embedding_deployment = embedding_deployment
        self.sourcepage_field = sourcepage_field
        self.content_field = content_field
        self.openai_gptv_deployment = openai_gptv_deployment
        self.gptv_model = gptv_model

    async def download_blob_as_base64(self, file_path: str) -> str:
        base_name, _ = os.path.splitext(file_path)
        blob = await self.blob_container_client.get_blob_client(base_name + ".png").download_blob()

        if not blob.properties or not blob.properties.has_key("content_settings"):
            return
        return base64.b64encode(await blob.readall()).decode("utf-8")

    async def generate_image_embeddings(self, text):
        endpoint = f"{os.environ['VISION_ENDPOINT']}/computervision/retrieval:vectorizeText"

        params = {"api-version": "2023-02-01-preview"}
        headers = {"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": os.environ["VISION_KEY"]}
        data = {"text": text}

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, params=params, headers=headers, json=data) as response:
                if response.status == 200:
                    json = await response.json()
                    return json["vector"]
                else:
                    print(f"Error: {response.status} - {response.text}")
                    return None

    # The SDK is yet to support multi dimensional vector search
    async def temp_search_fn_multi_vector(
        self,
        query_text,
        filter=None,
        query_type=None,
        query_language=None,
        query_speller=None,
        semantic_configuration_name=None,
        top=None,
        query_caption=None,
        vectors=None,
    ):
        endpoint = f"https://{os.environ['AZURE_SEARCH_SERVICE']}.search.windows.net/indexes/{os.environ['AZURE_SEARCH_INDEX']}/docs/search"
        params = {"api-version": "2023-07-01-Preview"}
        headers = {"Content-Type": "application/json", "api-key": os.environ["AZURE_SEARCH_SERVICE_KEY"]}
        data = {
            "search": query_text,
            "filter": filter,
            "queryType": query_type,
            "queryLanguage": query_language,
            "speller": query_speller,
            "semanticConfiguration": semantic_configuration_name,
            "top": top,
            "captions": query_caption,
            "vectors": vectors,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, params=params, headers=headers, json=data) as response:
                json = await response.json()
                return json["value"]

    # Place holder function. We will replace request with openai sdk when available
    async def gptv_request(self, data):
        base_url = f"https://{self.openai_gptv_deployment}.openai.azure.com/openai/deployments/{self.gptv_model}"
        endpoint = f"{base_url}/rainbow?api-version=2023-03-15-preview"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {openai.api_key}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, headers=headers, data=json.dumps(data)) as response:
                r = await response.json()
                combined_text = "".join(choice["text"] for choice in r["choices"])
                return combined_text

    def trim_embedding(self, embedding):
        """Format the embedding list to show the first 2 items followed by the count of the remaining items."""
        return f"[{embedding[0]}, {embedding[1]} ...+{len(embedding) - 2} more]" if len(embedding) > 2 else embedding

    def trim_embeddings_in_data(self, data):
        """Trim the embeddings in a list of data objects."""
        for item in data:
            if "embedding" in item:
                item["embedding"] = self.trim_embedding(item["embedding"])
            if "imageEmbedding" in item:
                item["imageEmbedding"] = self.trim_embedding(item.get("imageEmbedding", []))
        return data

    async def run(self, q: str, overrides: dict[str, Any]) -> ApproachResult:
        has_text = overrides.get("retrieval_mode") in ["text", "hybrid", None]
        has_vector = overrides.get("retrieval_mode") in ["vectors", "hybrid", None]
        vector_fields = overrides.get("vector_fields") or []
        use_gptv = overrides.get("use_gptv")

        include_gtpV_text = overrides.get("gptv_input") in ["textAndImages", "texts", None]
        include_gtpV_images = overrides.get("gptv_input") in ["textAndImages", "images", None]

        use_semantic_captions = True if overrides.get("semantic_captions") and has_text else False
        top = overrides.get("top") or 3
        exclude_category = overrides.get("exclude_category") or None
        filter = "category ne '{}'".format(exclude_category.replace("'", "''")) if exclude_category else None

        text_query_vector = None
        image_query_vector = None

        # If retrieval mode includes vectors, compute an embeddings for the query
        if has_vector:
            if "embedding" in vector_fields:
                text_query_vector = (await openai.Embedding.acreate(engine=self.embedding_deployment, input=q))["data"][
                    0
                ]["embedding"]

            if "imageEmbedding" in vector_fields:
                image_query_vector = await self.generate_image_embeddings(q)

        # Only keep the text query if the retrieval mode uses text, otherwise drop it
        query_text = q if has_text else None

        vectors = [
            {"value": vec, "fields": field, "k": 50}
            for vec, field in [(text_query_vector, "embedding"), (image_query_vector, "imageEmbedding")]
            if vec
        ]

        # Use semantic ranker if requested and if retrieval mode is text or hybrid (vectors + text)
        if overrides.get("semantic_ranker") and has_text:
            # r = self.search_client.search(query_text,
            #                               filter=filter,
            #                               query_type=QueryType.SEMANTIC,
            #                               query_language="en-us",
            #                               query_speller="lexicon",
            #                               semantic_configuration_name="default",
            #                               top=top,
            #                               query_caption="extractive|highlight-false" if use_semantic_captions else None,
            #                               vectors=vectors)
            r = await self.temp_search_fn_multi_vector(
                query_text,
                filter=filter,
                query_type=QueryType.SEMANTIC,
                query_language="en-us",
                query_speller="lexicon",
                semantic_configuration_name="default",
                top=top,
                query_caption="extractive|highlight-false" if use_semantic_captions else None,
                vectors=vectors,
            )

        else:
            # r = self.search_client.search(query_text,
            #                               filter=filter,
            #                               top=top,
            #                               vectors=vectors)
            r = await self.temp_search_fn_multi_vector(query_text, filter=filter, top=top, vectors=vectors)

        if use_semantic_captions:
            results = [
                (doc[self.sourcepage_field], nonewlines(" . ".join([c.text for c in doc["@search.captions"]])))
                for doc in r
            ]
        else:
            results = [(doc[self.sourcepage_field], nonewlines(doc[self.content_field])) for doc in r]

        trimmed_results = self.trim_embeddings_in_data(r)

        # GPT-V is yet to support chat completion.
        if use_gptv:
            data = {
                "transcript": [{"type": "text", "data": self.system_chat_template_gptv}, {"type": "text", "data": q}],
                "max_tokens": 1024,
                "temperature": overrides.get("temperature") or 0.7,
                "n": 1,
            }

            for source, text_result in results:
                data["transcript"].append(
                    {"type": "text", "data": ": ".join([source, text_result])}
                ) if include_gtpV_text else None
                data["transcript"].append(
                    {"type": "image", "data": await self.download_blob_as_base64(source)}
                ) if include_gtpV_images else None

            chat_content = await self.gptv_request(data)
            result_dict = {
                t: [item["data"] for item in data["transcript"] if item["type"] == t] for t in ["text", "image"]
            }
            text_results, image_results = result_dict["text"][2:], result_dict["image"]

            return ApproachResult(
                chat_content,
                {"text": text_results, "images": image_results},
                [
                    ThoughtStep(
                        "Search Query",
                        query_text,
                        {"vectorFields": vector_fields, "semanticCaptions": use_semantic_captions},
                    ),
                    ThoughtStep("Results", trimmed_results),
                    ThoughtStep("Prompt", data["transcript"]),
                ],
            )

        else:
            message_builder = MessageBuilder(
                overrides.get("prompt_template") or self.system_chat_template, self.chatgpt_model
            )

            # add user question
            user_content = (
                q + "\n" + "Sources:\n {content}".format(content="\n".join([": ".join(result) for result in results]))
            )
            message_builder.append_message("user", user_content)

            # Add shots/samples. This helps model to mimic response and make sure they match rules laid out in system message.
            message_builder.append_message("assistant", self.answer)
            message_builder.append_message("user", self.question)

            messages = message_builder.messages
            chat_completion = await openai.ChatCompletion.acreate(
                deployment_id=self.openai_deployment,
                model=self.chatgpt_model,
                messages=messages,
                temperature=overrides.get("temperature") or 0.3,
                max_tokens=1024,
                n=1,
            )

            return ApproachResult(
                chat_completion.choices[0].message.content,
                {"text": [": ".join(result) for result in results]},
                [
                    ThoughtStep(
                        "Search Query",
                        query_text,
                        {"vectorFields": vector_fields, "semanticCaptions": use_semantic_captions},
                    ),
                    ThoughtStep("Results", trimmed_results),
                    ThoughtStep("Prompt", [str(message) for message in messages]),
                ],
            )
