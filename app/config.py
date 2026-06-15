"""
Bilibili RAG 知识库系统

核心配置模块
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices, field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI / LLM 配置
    llm_provider: str = Field(default="dashscope", env="LLM_PROVIDER")
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DASHSCOPE_API_KEY", "OPENAI_API_KEY"),
    )
    dashscope_api_key: str = Field(
        default="",
        validation_alias="DASHSCOPE_API_KEY",
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", env="OPENAI_BASE_URL"
    )
    llm_model: str = Field(default="gpt-4-turbo", env="LLM_MODEL")
    deepseek_api_key: str = Field(default="", env="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1", env="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-chat", env="DEEPSEEK_MODEL")
    deepseek_thinking_config: str = Field(default="", env="DEEPSEEK_THINKING_CONFIG")
    openai_native_api_key: str = Field(default="", env="OPENAI_NATIVE_API_KEY")
    openai_native_base_url: str = Field(
        default="https://api.openai.com/v1", env="OPENAI_NATIVE_BASE_URL"
    )
    openai_native_model: str = Field(default="gpt-4o-mini", env="OPENAI_NATIVE_MODEL")
    openai_native_thinking_config: str = Field(
        default="", env="OPENAI_NATIVE_THINKING_CONFIG"
    )
    kimi_api_key: str = Field(default="", env="KIMI_API_KEY")
    kimi_base_url: str = Field(
        default="https://api.moonshot.cn/v1", env="KIMI_BASE_URL"
    )
    kimi_model: str = Field(default="moonshot-v1-8k", env="KIMI_MODEL")
    kimi_thinking_config: str = Field(default="", env="KIMI_THINKING_CONFIG")
    siliconflow_api_key: str = Field(default="", env="SILICONFLOW_API_KEY")
    siliconflow_base_url: str = Field(
        default="https://api.siliconflow.cn/v1", env="SILICONFLOW_BASE_URL"
    )
    siliconflow_model: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct", env="SILICONFLOW_MODEL"
    )
    siliconflow_thinking_config: str = Field(
        default="", env="SILICONFLOW_THINKING_CONFIG"
    )
    zhipu_api_key: str = Field(default="", env="ZHIPU_API_KEY")
    zhipu_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4", env="ZHIPU_BASE_URL"
    )
    zhipu_model: str = Field(default="glm-4-flash", env="ZHIPU_MODEL")
    zhipu_thinking_config: str = Field(default="", env="ZHIPU_THINKING_CONFIG")
    dashscope_thinking_config: str = Field(default="", env="DASHSCOPE_THINKING_CONFIG")
    embedding_model: str = Field(
        default="text-embedding-3-small", env="EMBEDDING_MODEL"
    )

    # DashScope ASR
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1", env="DASHSCOPE_BASE_URL"
    )
    asr_model: str = Field(default="paraformer-v2", env="ASR_MODEL")
    asr_timeout: int = Field(default=600, env="ASR_TIMEOUT")
    asr_model_local: str = Field(
        default="paraformer-realtime-v2", env="ASR_MODEL_LOCAL"
    )
    asr_input_format: str = Field(default="pcm", env="ASR_INPUT_FORMAT")

    # 应用配置
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    debug: bool = Field(default=True, env="DEBUG")

    # 数据库
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/bilibili_rag.db", env="DATABASE_URL"
    )

    # ChromaDB
    chroma_persist_directory: str = Field(
        default="./data/chroma_db", env="CHROMA_PERSIST_DIRECTORY"
    )

    # Google OAuth
    google_client_id: str = Field(default="", env="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="", env="GOOGLE_REDIRECT_URI")

    # WeChat OAuth
    wechat_client_id: str = Field(default="", env="WECHAT_CLIENT_ID")
    wechat_client_secret: str = Field(default="", env="WECHAT_CLIENT_SECRET")
    wechat_redirect_uri: str = Field(default="", env="WECHAT_REDIRECT_URI")

    # QQ OAuth
    qq_client_id: str = Field(default="", env="QQ_CLIENT_ID")
    qq_client_secret: str = Field(default="", env="QQ_CLIENT_SECRET")
    qq_redirect_uri: str = Field(default="", env="QQ_REDIRECT_URI")

    # HTTP 代理（访问 Google 等境外服务时需要）
    http_proxy: str = Field(default="", env="HTTP_PROXY")

    # SMTP 邮件配置（用于发送邮箱验证码）
    smtp_host: str = Field(default="smtp.qq.com", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: str = Field(default="", env="SMTP_USER")
    smtp_password: str = Field(default="", env="SMTP_PASSWORD")
    smtp_from: str = Field(default="", env="SMTP_FROM")
    smtp_use_tls: bool = Field(default=True, env="SMTP_USE_TLS")

    @field_validator("deepseek_model", mode="before")
    @classmethod
    def normalize_deepseek_model(cls, value: str) -> str:
        """兼容常见 DeepSeek 模型别名，避免因拼写差异报 400。"""
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        alias_map = {
            "deepseek-v4pro": "deepseek-v4-pro",
            "deepseek-v4_pro": "deepseek-v4-pro",
            "deepseekv4pro": "deepseek-v4-pro",
            "deepseek-v4flash": "deepseek-v4-flash",
            "deepseek-v4_flash": "deepseek-v4-flash",
            "deepseekv4flash": "deepseek-v4-flash",
        }
        return alias_map.get(normalized, value.strip())


# 全局配置实例
settings = Settings()


def ensure_directories():
    """确保必要的目录存在"""
    dirs = ["data", settings.chroma_persist_directory, "logs"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
