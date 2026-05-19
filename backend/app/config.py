from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://geolens:geolens@db:5432/geolens"
    redis_url: str = "redis://redis:6379"
    openai_api_key: str = ""
    groq_api_key: str = ""
    jaeger_endpoint: str = "http://jaeger:4317"
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    groq_chat_model: str = "llama-3.3-70b-versatile"
    sample_data_path: str = "/sample_data/nyc_chunks.json"
    eval_data_path: str = "/sample_data/eval_queries.json"
    enable_reranker: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_hyde: bool = True
    enable_query_expansion: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
