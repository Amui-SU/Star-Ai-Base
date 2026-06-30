"""Cookie helpers for constructing authenticated Bilibili services."""

from collections.abc import Mapping
from typing import Any, TypeVar

ServiceT = TypeVar("ServiceT")


def service_kwargs_from_cookies(cookies: Mapping[str, Any] | None) -> dict[str, Any]:
    cookies = cookies or {}
    return {
        "sessdata": cookies.get("SESSDATA") or cookies.get("sessdata"),
        "bili_jct": cookies.get("bili_jct"),
        "dedeuserid": (
            cookies.get("DedeUserID")
            or cookies.get("dedeuserid")
            or cookies.get("Dedeuserid")
        ),
    }


def normalize_bilibili_cookies(cookies: Mapping[str, Any] | None) -> dict[str, Any]:
    kwargs = service_kwargs_from_cookies(cookies)
    return {
        "SESSDATA": kwargs["sessdata"],
        "bili_jct": kwargs["bili_jct"],
        "DedeUserID": kwargs["dedeuserid"],
    }


def bilibili_service_from_cookies(
    cookies: Mapping[str, Any] | None,
    service_cls: type[ServiceT],
) -> ServiceT:
    return service_cls(**service_kwargs_from_cookies(cookies))
