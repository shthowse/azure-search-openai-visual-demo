import asyncio
import os
from typing import Any

import openai
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import QueryType, Vector
from azure.storage.blob import ContainerClient

from approaches.approach import ApproachResult, AskApproach, ThoughtStep
from core.embeddingshelper import generate_image_embeddings, serialize_data
from core.imageshelper import fetch_image
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
        "You are an intelligent assistant helping analyze the Annual Financial Report of Contoso Ltd., The documents contain text, graphs, tables and images. "
        + "Answer the following question using only the data provided in the sources below. "
        + "For tabular information return it as an html table. Do not return markdown format. "
        + "Each text source has a name followed by colon and the actual information, always include the source name for each fact you use in the response. [filename]"
        + "Each image source has the file name in the top left corner of the image with coordinates (10,10) pixels and is in the format SourceFileName:<file_name>, always include the file name in the format [file_name] when a image is used "
        + "The text and image source can be the same file name, don't use the image title when citing the image source, only use the file name as mentioned "
        + "If you cannot answer using the sources below, say you don't know. Return just the answer without any input texts"
    )

    def __init__(
        self,
        search_client: SearchClient,
        blob_container_client: ContainerClient,
        chatgpt_deployment: str,
        chatgpt_model: str,
        gptv_deployment: str,
        gptv_model: str,
        embedding_deployment: str,
        sourcepage_field: str,
        content_field: str,
    ):
        self.search_client = search_client
        self.blob_container_client = blob_container_client
        self.chatgpt_deployment = chatgpt_deployment
        self.chatgpt_model = chatgpt_model
        self.embedding_deployment = embedding_deployment
        self.sourcepage_field = sourcepage_field
        self.content_field = content_field
        self.gptv_deployment = gptv_deployment
        self.gptv_model = gptv_model

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
        vectors = []
        if has_vector:
            if "embedding" in vector_fields:
                text_query_vector = (await openai.Embedding.acreate(engine=self.embedding_deployment, input=q))["data"][
                    0
                ]["embedding"]
                vectors.append(Vector(value=text_query_vector, k=50, fields="embedding"))
            if "imageEmbedding" in vector_fields:
                image_query_vector = await generate_image_embeddings(q)
                vectors.append(Vector(value=image_query_vector, k=50, fields="imageEmbedding"))

        # Only keep the text query if the retrieval mode uses text, otherwise drop it
        query_text = q if has_text else None

        # Use semantic ranker if requested and if retrieval mode is text or hybrid (vectors + text)
        if overrides.get("semantic_ranker") and has_text:
            r = await self.search_client.search(
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
            r = await self.search_client.search(query_text, filter=filter, top=top, vectors=vectors)

        results = []
        trimmed_results = []

        async for page in r.by_page():
            async for doc in page:
                if use_semantic_captions:
                    caption_text = " . ".join([c.text for c in doc["@search.captions"]])
                    results.append((doc[self.sourcepage_field], nonewlines(caption_text)))
                else:
                    results.append((doc[self.sourcepage_field], nonewlines(doc[self.content_field])))

                trimmed_results.append(serialize_data(doc))

        image_list = []
        user_content = [q]

        template = overrides.get("prompt_template") or (
            self.system_chat_template_gptv if use_gptv else self.system_chat_template
        )
        model = self.gptv_model if use_gptv else self.chatgpt_model
        message_builder = MessageBuilder(template, model)

        # Process results
        sources_content = "Sources:\n" + "\n".join([": ".join(result) for result in results])
        if include_gtpV_text and use_gptv:
            user_content.append(sources_content)
        if include_gtpV_images and use_gptv:
            image_list.extend(
                await asyncio.gather(*(fetch_image(self.blob_container_client, result) for result in results))
            )
            user_content.extend(image_list)

        # Append user message
        if use_gptv:
            message_builder.append_message("user", user_content)
        else:
            user_content = q + "\n" + sources_content
            message_builder.append_message("user", user_content)
            message_builder.append_message("assistant", self.answer)
            message_builder.append_message("user", self.question)

        messages = message_builder.messages

        # Chat completion
        engine = self.gptv_deployment if use_gptv else self.chatgpt_deployment
        temperature = overrides.get("temperature") or (0.7 if use_gptv else 0.3)

        chat_completion = await openai.ChatCompletion.acreate(
            engine=engine,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
            n=1,
        )

        data_points = {"text": [": ".join(result) for result in results]}
        if use_gptv:
            data_points["images"] = [d["image"] for d in image_list]

        return ApproachResult(
            chat_completion.choices[0].message.content,
            data_points,
            [
                ThoughtStep(
                    "Search Query",
                    query_text,
                    {"vectorFields": vector_fields if has_vector else [], "semanticCaptions": use_semantic_captions},
                ),
                ThoughtStep("Results", trimmed_results),
                ThoughtStep("Prompt", [str(message) for message in messages]),
            ],
        )
