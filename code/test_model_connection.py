from langchain_openai import OpenAIEmbeddings

emb_model = OpenAIEmbeddings(
            model="Qwen3-Embedding-0.6B",
            api_key="EMPTY",
            base_url="http://0.0.0.0:8007/v1",
#            tiktoken_enabled=False,
            check_embedding_ctx_length=False
        )

print(emb_model.embed_query("Hello world"))
