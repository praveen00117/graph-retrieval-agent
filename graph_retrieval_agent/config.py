from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_query_url: str
    neo4j_username: str
    neo4j_password: str

    openai_api_key: str
    openai_model: str = "gpt-5.6-luna"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()