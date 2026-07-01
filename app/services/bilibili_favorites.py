"""Favorite folder API helpers for Bilibili."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import httpx


ParseJsonResponse = Callable[[httpx.Response, str], dict[str, Any]]


async def get_bilibili_user_favorites(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    parse_json_response: ParseJsonResponse,
    mid: int | str | None,
) -> list[dict[str, Any]]:
    """Fetch all favorite folders for a Bilibili user."""
    if not mid:
        raise Exception("未指定用户 ID")

    url = f"{base_url}/x/v3/fav/folder/created/list-all"
    params = {"up_mid": mid}

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.get(url, params=params, cookies=dict(cookies))
            data = parse_json_response(response, "获取收藏夹")
            break
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.TransportError,
        ) as exc:
            last_error = exc
            if attempt == 2:
                raise Exception("连接 B站收藏夹接口超时或网络异常，请稍后重试") from exc
            await asyncio.sleep(0.8 * (attempt + 1))
    else:
        raise last_error or Exception("连接 B站收藏夹接口失败")

    if data["code"] != 0:
        message = data.get("message") or data.get("msg") or "未知错误"
        if data.get("code") in {-101, -400, -403}:
            raise Exception(
                f"获取收藏夹失败: B站登录态可能已失效，请重新扫码登录（{message}）"
            )
        raise Exception(f"获取收藏夹失败: {message}")

    return data["data"]["list"] or []


async def get_bilibili_favorite_content(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    parse_json_response: ParseJsonResponse,
    media_id: int,
    pn: int = 1,
    ps: int = 20,
) -> dict[str, Any]:
    """Fetch one page of favorite folder content."""
    url = f"{base_url}/x/v3/fav/resource/list"
    params = {"media_id": media_id, "pn": pn, "ps": min(ps, 20), "platform": "web"}

    response = await client.get(url, params=params, cookies=dict(cookies))
    data = parse_json_response(response, "获取收藏夹内容")

    if data["code"] != 0:
        raise Exception(f"获取收藏夹内容失败: {data['message']}")

    return {
        "info": data["data"]["info"],
        "medias": data["data"]["medias"] or [],
        "has_more": data["data"]["has_more"],
    }


async def get_all_bilibili_favorite_videos(
    *,
    media_id: int,
    load_content: Callable[..., Awaitable[dict[str, Any]]],
    sleep: Callable[[float], Awaitable[Any] | Any] = asyncio.sleep,
) -> list[dict[str, Any]]:
    """Fetch every video from a favorite folder by following Bilibili pagination."""
    all_videos: list[dict[str, Any]] = []
    pn = 1

    while True:
        result = await load_content(media_id, pn=pn, ps=20)
        all_videos.extend(result["medias"])

        if not result["has_more"]:
            break
        pn += 1

        maybe_awaitable = sleep(0.3)
        if hasattr(maybe_awaitable, "__await__"):
            await maybe_awaitable

    return all_videos


async def move_bilibili_favorite_resources(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    bili_jct: str | None,
    dedeuserid: str | None,
    src_media_id: int,
    tar_media_id: int,
    resources: Sequence[str],
) -> dict[str, Any]:
    """Move favorite resources between Bilibili favorite folders."""
    if not bili_jct:
        raise Exception("缺少 bili_jct，无法进行收藏夹移动")

    if not resources:
        return {"moved": 0}

    url = f"{base_url}/x/v3/fav/resource/move"
    data: dict[str, Any] = {
        "src_media_id": src_media_id,
        "tar_media_id": tar_media_id,
        "resources": ",".join(resources),
        "csrf": bili_jct,
    }
    if dedeuserid:
        data["mid"] = dedeuserid

    response = await client.post(url, data=data, cookies=dict(cookies))
    result = response.json()
    if result.get("code") != 0:
        raise Exception(f"移动收藏夹内容失败: {result.get('message')}")
    return result.get("data") or {}


async def clean_bilibili_favorite_resources(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    bili_jct: str | None,
    media_id: int,
) -> dict[str, Any]:
    """Clean invalid resources in a Bilibili favorite folder."""
    if not bili_jct:
        raise Exception("缺少 bili_jct，无法清理失效内容")

    url = f"{base_url}/x/v3/fav/resource/clean"
    data = {"media_id": media_id, "csrf": bili_jct}
    response = await client.post(url, data=data, cookies=dict(cookies))
    result = response.json()
    if result.get("code") != 0:
        raise Exception(f"清理失效内容失败: {result.get('message')}")
    return result.get("data") or {}
