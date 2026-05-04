import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()


class AppConfig(BaseModel):
    # LLM配置
    llm_provider: str = "dashscope"

    # Ollama配置
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # vLLM配置
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    vllm_api_key: str = "EMPTY"

    # 阿里百炼(DashScope)配置
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: str | None = None
    dashscope_model: str | None = None

    # Embedding模型配置
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # vLLM Embedding配置
    vllm_embedding_base_url: str = "http://localhost:8000/v1"
    vllm_embedding_model: str = "BAAI/bge-large-zh-v1.5"
    vllm_embedding_api_key: str = "EMPTY"

    # 阿里百炼Embedding配置
    dashscope_embedding_model: str | None = None

    # 数据库配置
    db_type: str = "sqlite"
    db_path: str = "./database/ecommerce.db"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ecommerce"
    db_user: str = "user"
    db_password: str = ""

    # 应用配置
    debug: bool = False
    max_retry_attempts: int = 3

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("ollama", "vllm", "dashscope"):
            raise ValueError(f"LLM_PROVIDER must be 'ollama', 'vllm', or 'dashscope', got: {v}")
        return v

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        if v not in ("sentence-transformers", "huggingface", "vllm", "dashscope"):
            raise ValueError(f"EMBEDDING_PROVIDER must be 'sentence-transformers', 'huggingface', 'vllm', or 'dashscope', got: {v}")
        return v

    @field_validator("db_type")
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        if v not in ("sqlite", "mysql", "postgresql"):
            raise ValueError(f"DB_TYPE must be sqlite/mysql/postgresql, got: {v}")
        return v


def load_config() -> AppConfig:
    return AppConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        vllm_base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
        vllm_model=os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        vllm_api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
        dashscope_base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
        dashscope_model=os.getenv("DASHSCOPE_MODEL", "qwen-plus"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "sentence-transformers"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
        vllm_embedding_base_url=os.getenv("VLLM_EMBEDDING_BASE_URL", "http://localhost:8000/v1"),
        vllm_embedding_model=os.getenv("VLLM_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
        vllm_embedding_api_key=os.getenv("VLLM_EMBEDDING_API_KEY", "EMPTY"),
        dashscope_embedding_model=os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3"),
        db_type=os.getenv("DB_TYPE", "sqlite"),
        db_path=os.getenv("DB_PATH", "./database/ecommerce.db"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "ecommerce"),
        db_user=os.getenv("DB_USER", "user"),
        db_password=os.getenv("DB_PASSWORD", ""),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
    )


config = load_config()

# 全局单例缓存
_llm_instance = None
_embedding_model_instance = None


def get_embedding_model():
    """获取embedding模型实例（单例模式）"""
    global _embedding_model_instance

    if _embedding_model_instance is not None:
        return _embedding_model_instance

    if config.embedding_provider == "sentence-transformers":
        from sentence_transformers import SentenceTransformer
        _embedding_model_instance = SentenceTransformer(config.embedding_model)
    elif config.embedding_provider == "huggingface":
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embedding_model_instance = HuggingFaceEmbeddings(
            model_name=config.embedding_model
        )
    elif config.embedding_provider == "vllm":
        from langchain_openai import OpenAIEmbeddings
        _embedding_model_instance = OpenAIEmbeddings(
            model=config.vllm_embedding_model,
            api_key=config.vllm_embedding_api_key,
            base_url=config.vllm_embedding_base_url
        )
    elif config.embedding_provider == "dashscope":
        from langchain_community.embeddings import DashScopeEmbeddings
        _embedding_model_instance = DashScopeEmbeddings(
            model=config.dashscope_embedding_model,
            dashscope_api_key=config.dashscope_api_key
        )
    else:
        raise ValueError(f"Unsupported embedding provider: {config.embedding_provider}")

    return _embedding_model_instance


def get_llm():
    """获取LLM实例（单例模式）"""
    global _llm_instance

    if _llm_instance is not None:
        return _llm_instance

    if config.llm_provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        _llm_instance = ChatOllama(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
            temperature=0,
        )
    elif config.llm_provider == "vllm":
        from langchain_openai import ChatOpenAI
        _llm_instance = ChatOpenAI(
            base_url=config.vllm_base_url,
            api_key=config.vllm_api_key,
            model=config.vllm_model,
            temperature=0,
            max_tokens=4096,
        )
    elif config.llm_provider == "dashscope":
        from langchain_qwq import ChatQwen
        _llm_instance = ChatQwen(
            base_url=config.dashscope_base_url,
            model=config.dashscope_model,
            api_key=config.dashscope_api_key,
            temperature=0,
            max_tokens=4096,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")

    return _llm_instance
