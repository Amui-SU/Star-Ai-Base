"""Video API helpers for Bilibili."""

from typing import Any, Mapping, Optional

from loguru import logger

from app.services.bilibili_media import select_audio_url_from_playurl_payload
from app.services.wbi import wbi_signer as default_wbi_signer


async def get_bilibili_video_info(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    bvid: str,
) -> dict[str, Any]:
    """Fetch Bilibili video detail payload."""
    url = f"{base_url}/x/web-interface/view"
    response = await client.get(url, params={"bvid": bvid}, cookies=dict(cookies))
    data = response.json()

    if data["code"] != 0:
        raise Exception(f"获取视频信息失败: {data['message']}")

    return data["data"]


async def get_bilibili_video_summary(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    bvid: str,
    cid: int,
    up_mid: int | None = None,
    wbi_signer: Any = default_wbi_signer,
) -> Optional[dict[str, Any]]:
    """Fetch Bilibili AI summary for a video."""
    url = f"{base_url}/x/web-interface/view/conclusion/get"

    params: dict[str, Any] = {
        "bvid": bvid,
        "cid": cid,
    }
    if up_mid:
        params["up_mid"] = up_mid

    signed_params = await wbi_signer.sign(params, cookies=dict(cookies))
    response = await client.get(url, params=signed_params, cookies=dict(cookies))
    data = response.json()

    if data["code"] != 0:
        logger.warning(
            f"获取视频摘要失败 [{bvid}]: {data.get('message', 'unknown error')}"
        )
        return None

    return data["data"]


async def get_bilibili_player_info(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    bvid: str,
    cid: int,
    aid: int | None = None,
    wbi_signer: Any = default_wbi_signer,
) -> Optional[dict[str, Any]]:
    """Fetch Bilibili player info, preferring the WBI endpoint."""
    params: dict[str, Any] = {
        "bvid": bvid,
        "cid": cid,
    }
    if aid:
        params["aid"] = aid

    cookie_payload = dict(cookies)
    cookies_for_sign = cookie_payload if cookie_payload else None

    try:
        signed_params = await wbi_signer.sign(params, cookies=cookies_for_sign)
        wbi_url = f"{base_url}/x/player/wbi/v2"
        response = await client.get(
            wbi_url, params=signed_params, cookies=cookie_payload
        )
        data = response.json()
        if data.get("code") == 0:
            return data.get("data")
        logger.warning(
            f"WBI 播放器信息失败 [{bvid}]: {data.get('message', 'unknown error')}"
        )
    except Exception as exc:
        logger.warning(f"WBI 播放器信息异常 [{bvid}]: {exc}")

    url = f"{base_url}/x/player/v2"
    response = await client.get(url, params=params, cookies=cookie_payload)
    data = response.json()

    if data["code"] != 0:
        logger.warning(
            f"获取播放器信息失败 [{bvid}]: {data.get('message', 'unknown error')}"
        )
        return None

    return data["data"]


async def get_bilibili_audio_url(
    *,
    client: Any,
    base_url: str,
    cookies: Mapping[str, str],
    bvid: str,
    cid: int,
    wbi_signer: Any = default_wbi_signer,
) -> Optional[str]:
    """Fetch an audio stream URL from Bilibili playurl endpoints."""
    params = {
        "bvid": bvid,
        "cid": cid,
        "fnval": 16,
        "fnver": 0,
        "fourk": 1,
    }

    cookie_payload = dict(cookies)
    cookies_for_sign = cookie_payload if cookie_payload else None

    try:
        signed_params = await wbi_signer.sign(params, cookies=cookies_for_sign)
        url = f"{base_url}/x/player/wbi/playurl"
        response = await client.get(url, params=signed_params, cookies=cookie_payload)
        data = response.json()
    except Exception as exc:
        logger.warning(f"获取音频信息失败(WBI) [{bvid}]: {exc}")
        data = None

    if not data or data.get("code") != 0:
        try:
            url = f"{base_url}/x/player/playurl"
            response = await client.get(url, params=params, cookies=cookie_payload)
            data = response.json()
        except Exception as exc:
            logger.warning(f"获取音频信息失败 [{bvid}]: {exc}")
            return None

    if data.get("code") != 0:
        logger.warning(
            f"获取音频信息失败 [{bvid}]: {data.get('message', 'unknown error')}"
        )
        return None

    payload = data.get("data") or {}
    return select_audio_url_from_playurl_payload(payload)
