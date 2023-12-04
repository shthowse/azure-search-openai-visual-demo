import logging
from typing import Any, Optional

import openai
from azure.search.documents.aio import SearchClient
from azure.storage.blob.aio import ContainerClient

from approaches.approach import ThoughtStep
from approaches.chatapproach import ChatApproach
from core.imageshelper import fetch_image
from core.messagebuilder import MessageBuilder
from core.modelhelper import get_token_limit


class ChatReadRetrieveReadVisionApproach(ChatApproach):

    """
    A multi-step approach that first uses OpenAI to turn the user's question into a search query,
    then uses Azure AI Search to retrieve relevant documents, and then sends the conversation history,
    original user question, and search results to OpenAI to generate a response.
    """

    def __init__(
        self,
        search_client: SearchClient,
        blob_container_client: ContainerClient,
        openai_host: str,
        gpt4v_deployment: Optional[str],  # Not needed for non-Azure OpenAI
        gpt4v_model: str,
        chatgpt_deployment: Optional[str],  # Not needed for non-Azure OpenAI
        chatgpt_model: str,
        embedding_deployment: Optional[str],  # Not needed for non-Azure OpenAI or for retrieval_mode="text"
        embedding_model: str,
        sourcepage_field: str,
        content_field: str,
        query_language: str,
        query_speller: str,
    ):
        self.search_client = search_client
        self.blob_container_client = blob_container_client
        self.openai_host = openai_host
        self.gpt4v_deployment = gpt4v_deployment
        self.gpt4v_model = gpt4v_model
        self.chatgpt_deployment = chatgpt_deployment
        self.chatgpt_model = chatgpt_model
        self.embedding_deployment = embedding_deployment
        self.embedding_model = embedding_model
        self.sourcepage_field = sourcepage_field
        self.content_field = content_field
        self.query_language = query_language
        self.query_speller = query_speller
        self.chatgpt_token_limit = get_token_limit(gpt4v_model)

    @property
    def system_message_chat_conversation(self):
        return """
        You are an intelligent assistant helping analyze the Annual Financial Report of Contoso Ltd., The documents contain text, graphs, tables and images.
        Each image source has the file name in the top left corner of the image with coordinates (10,10) pixels and is in the format SourceFileName:<file_name>
        Each text source starts in a new line and has the file name followed by colon and the actual information
        Always include the source name from the image or text for each fact you use in the response in the format: [filename]
        Answer the following question using only the data provided in the sources below.
        If asking a clarifying question to the user would help, ask the question.
        Be brief in your answers.
        For tabular information return it as an html table. Do not return markdown format.
        The text and image source can be the same file name, don't use the image title when citing the image source, only use the file name as mentioned
        If you cannot answer using the sources below, say you don't know. Return just the answer without any input texts. 
        {follow_up_questions_prompt}
        {injected_prompt}
        """

    async def run_until_final_call(
        self,
        history: list[dict[str, str]],
        overrides: dict[str, Any],
        auth_claims: dict[str, Any],
        should_stream: bool = False,
    ) -> tuple:
        has_text = overrides.get("retrieval_mode") in ["text", "hybrid", None]
        has_vector = overrides.get("retrieval_mode") in ["vectors", "hybrid", None]
        use_semantic_captions = True if overrides.get("semantic_captions") and has_text else False
        top = overrides.get("top", 3)
        filter = self.build_filter(overrides, auth_claims)
        use_semantic_ranker = True if overrides.get("semantic_ranker") and has_text else False

        include_gtpV_text = overrides.get("gpt4v_input") in ["textAndImages", "texts", None]
        include_gtpV_images = overrides.get("gpt4v_input") in ["textAndImages", "images", None]

        original_user_query = history[-1]["content"]

        # STEP 1: Generate an optimized keyword search query based on the chat history and the last question
        user_query_request = ["Generate search query for: " + original_user_query]
        messages = self.get_messages_from_history(
            system_prompt=self.query_prompt_template,
            model_id=self.chatgpt_model,
            history=history,
            user_content=user_query_request,
            max_tokens=self.chatgpt_token_limit - len(" ".join(user_query_request)),
            few_shots=self.query_prompt_few_shots,
        )

        chatgpt_args = {"deployment_id": self.gpt4v_deployment} if self.openai_host == "azure" else {}

        chat_completion = await openai.ChatCompletion.acreate(
            **chatgpt_args,
            messages=messages,
            temperature=0.0,
            max_tokens=100,  # Setting too low risks malformed JSON, setting too high may affect performance
            n=1,
        )

        query_text = self.get_search_query(chat_completion, original_user_query)

        # STEP 2: Retrieve relevant documents from the search index with the GPT optimized query

        # If retrieval mode includes vectors, compute an embeddings for the query
        vectors = []
        if has_vector:
            vectors.append(await self.compute_text_embedding(query_text))

        # Only keep the text query if the retrieval mode uses text, otherwise drop it
        if not has_text:
            query_text = None

        results = await self.search(top, query_text, filter, vectors, use_semantic_ranker, use_semantic_captions)

        content = "\n".join(result.content or "" for result in results)

        # STEP 3: Generate a contextual and content specific answer using the search results and chat history

        # Allow client to replace the entire prompt, or to inject into the exiting prompt using >>>
        system_message = self.get_system_prompt(
            overrides.get("prompt_template"),
            self.follow_up_questions_prompt_content if overrides.get("suggest_followup_questions") else "",
        )

        response_token_limit = 1024
        messages_token_limit = self.chatgpt_token_limit - response_token_limit

        user_content = [original_user_query]
        image_list = []

        if include_gtpV_text:
            user_content.append("\n\nSources:\n" + content)
        if include_gtpV_images:
            for result in results:
                image_list.append({"image": await fetch_image(self.blob_container_client, result)})
            user_content.extend(image_list)

        messages = self.get_messages_from_history(
            system_prompt=system_message,
            model_id=self.gpt4v_model,
            history=history,
            user_content=user_content,
            max_tokens=messages_token_limit,
        )

        data_points = {"text": [result.content or "" for result in results], "images": [d["image"] for d in image_list]}

        extra_info = {
            "data_points": data_points,
            "thoughts": [
                ThoughtStep(
                    "Search Query",
                    query_text,
                    {
                        "semanticCaptions": use_semantic_captions,
                        "Model ID": self.gpt4v_deployment,
                    },
                ),
                ThoughtStep("Results", [result.serialize_for_results() for result in results]),
                ThoughtStep("Prompt", [str(message) for message in messages]),
            ],
        }

        chatgpt4v_args = {"deployment_id": self.gpt4v_deployment} if self.openai_host == "azure" else {}
        chat_coroutine = openai.ChatCompletion.acreate(
            **chatgpt4v_args,
            messages=messages,
            temperature=overrides.get("temperature") or 0.7,
            max_tokens=response_token_limit,
            n=1,
            stream=should_stream,
        )
        return (extra_info, chat_coroutine)

    def get_messages_from_history(
        self,
        system_prompt: str,
        model_id: str,
        history: list[dict[str, str]],
        user_content: list[Any],
        max_tokens: int,
        few_shots=[],
    ) -> list:
        message_builder = MessageBuilder(system_prompt, model_id)

        for shot in reversed(few_shots):
            message_builder.concat_content(shot.get("role"), shot.get("content"))

        append_index = len(few_shots) + 1

        message_builder.concat_content(self.USER, user_content, index=append_index)
        total_token_count = message_builder.count_tokens_for_message(message_builder.messages[-1])

        newest_to_oldest = list(reversed(history[:-1]))
        for message in newest_to_oldest:
            potential_message_count = message_builder.count_tokens_for_message(message)
            if (total_token_count + potential_message_count) > max_tokens:
                logging.debug("Reached max tokens of %d, history will be truncated", max_tokens)
                break
            message_builder.concat_content(message["role"], message["content"], index=append_index)
            total_token_count += potential_message_count
        return message_builder.messages
