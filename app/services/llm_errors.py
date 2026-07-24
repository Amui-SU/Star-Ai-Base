"""Safe classification for model and upstream service failures."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SafeUpstreamError:
    code: str
    message: str

    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}

    def log_message(self, context: str) -> str:
        return f"{context} [{self.code}]"


def classify_upstream_error(exc: Exception) -> SafeUpstreamError:
    text = str(exc).lower()
    class_name = type(exc).__name__.lower()

    if "socksio" in text or "httpx[socks]" in text or "socks proxy" in text:
        return SafeUpstreamError(
            "socks_proxy_dependency_missing",
            "SOCKS 代理依赖缺失（socksio）",
        )
    if isinstance(exc, TimeoutError) or "timeout" in text or "timed out" in text:
        return SafeUpstreamError("upstream_timeout", "上游模型服务请求超时")
    if any(
        marker in text or marker in class_name
        for marker in ("authentication", "unauthorized", "permission", "api key")
    ):
        return SafeUpstreamError(
            "upstream_authentication_failed",
            "上游模型服务认证失败",
        )
    if "tool" in text and any(
        marker in text for marker in ("not support", "unsupported", "not supported")
    ):
        return SafeUpstreamError(
            "upstream_tools_unsupported",
            "上游模型服务不支持工具调用",
        )
    if any(
        marker in text or marker in class_name
        for marker in ("connection", "connecterror", "network")
    ):
        return SafeUpstreamError(
            "upstream_connection_failed",
            "上游模型服务连接失败",
        )
    if any(marker in text for marker in ("rate limit", "overloaded", "unavailable")):
        return SafeUpstreamError(
            "upstream_model_unavailable",
            "上游模型服务暂不可用",
        )
    return SafeUpstreamError(
        "upstream_request_failed",
        "上游模型服务请求失败",
    )
