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
    llm_provider: str = Field(default="dashscope")
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DASHSCOPE_API_KEY", "OPENAI_API_KEY"),
    )
    dashscope_api_key: str = Field(
        default="",
        validation_alias="DASHSCOPE_API_KEY",
    )
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    llm_model: str = Field(default="gpt-4-turbo")
    deepseek_api_key: str = Field(default="")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1")
    deepseek_model: str = Field(default="deepseek-chat")
    deepseek_thinking_config: str = Field(default="")
    openai_native_api_key: str = Field(default="")
    openai_native_base_url: str = Field(default="https://api.openai.com/v1")
    openai_native_model: str = Field(default="gpt-4o-mini")
    openai_native_thinking_config: str = Field(default="")
    kimi_api_key: str = Field(default="")
    kimi_base_url: str = Field(default="https://api.moonshot.cn/v1")
    kimi_model: str = Field(default="moonshot-v1-8k")
    kimi_thinking_config: str = Field(default="")
    siliconflow_api_key: str = Field(default="")
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1")
    siliconflow_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct")
    siliconflow_thinking_config: str = Field(default="")
    zhipu_api_key: str = Field(default="")
    zhipu_base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4")
    zhipu_model: str = Field(default="glm-4-flash")
    zhipu_thinking_config: str = Field(default="")
    dashscope_thinking_config: str = Field(default="")
    embedding_model: str = Field(default="text-embedding-3-small")

    # DashScope ASR
    dashscope_base_url: str = Field(default="https://dashscope.aliyuncs.com/api/v1")
    asr_model: str = Field(default="paraformer-v2")
    asr_timeout: int = Field(default=600)
    asr_model_local: str = Field(default="paraformer-realtime-v2")
    asr_input_format: str = Field(default="pcm")

    # 应用配置
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    debug: bool = Field(default=False)
    session_cookie_secure: Optional[bool] = Field(
        default=None,
    )

    # 数据库
    database_url: str = Field(default="sqlite+aiosqlite:///./data/bilibili_rag.db")

    # ChromaDB
    chroma_persist_directory: str = Field(default="./data/chroma_db")

    # Google OAuth
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="")

    # WeChat OAuth
    wechat_client_id: str = Field(default="")
    wechat_client_secret: str = Field(default="")
    wechat_redirect_uri: str = Field(default="")

    # QQ OAuth
    qq_client_id: str = Field(default="")
    qq_client_secret: str = Field(default="")
    qq_redirect_uri: str = Field(default="")

    # HTTP 代理（访问 Google 等境外服务时需要）
    http_proxy: str = Field(default="")

    # Web search provider configuration.
    web_search_provider: str = Field(default="html")
    tavily_api_key: str = Field(default="")
    web_search_fallback_html: bool = Field(default=True)
    tavily_search_depth: str = Field(default="basic")

    # SMTP 邮件配置（用于发送邮箱验证码）
    smtp_host: str = Field(default="smtp.qq.com")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    smtp_use_tls: bool = Field(default=True)

    # 管理员账号。为空时首个注册用户自动成为管理员；多个邮箱用英文逗号分隔。
    admin_emails: str = Field(default="")

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
