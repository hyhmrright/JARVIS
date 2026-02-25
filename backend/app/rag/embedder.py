from langchain_openai import OpenAIEmbeddings


def get_embedder(api_key: str) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key,  # type: ignore[call-arg]
    )
