from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import FavoriteFolder, FavoriteVideo, VideoCache, VideoNote


async def _send_code(client, email: str) -> str:
    response = await client.post("/system-auth/send-code", json={"email": email})
    assert response.status_code == 200
    return response.json()["code"]


async def _register_user(client, email: str, display_name: str) -> dict:
    code = await _send_code(client, email)
    response = await client.post(
        "/system-auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
            "code": code,
        },
    )
    assert response.status_code == 200
    return response.json()


async def _create_knowledge_base(client, name: str, headers: dict) -> dict:
    response = await client.post(
        "/knowledge-bases",
        json={"name": name},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


async def _seed_video(
    db_session_factory,
    *,
    workspace_id: int,
    knowledge_base_id: int,
    bvid: str = "BVNOTE123",
    cid: int | None = None,
    title: str = "AI 视频学习法",
    folder_title: str = "学习收藏夹",
    duration: int | None = 360,
    outline_json: list | None = None,
    subtitle_timeline_json: list | None = None,
    page_number: int | None = None,
    part_title: str | None = None,
    total_parts: int | None = None,
):
    if outline_json is None:
        outline_json = [
            {
                "title": "开场",
                "timestamp": 12,
                "points": [{"content": "介绍学习目标", "timestamp": 24}],
            }
        ]
    async with db_session_factory() as session:
        folder = FavoriteFolder(
            session_id=f"note-session-{knowledge_base_id}",
            media_id=9001,
            title=folder_title,
            media_count=1,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=None,
        )
        session.add(folder)
        await session.flush()
        session.add(
            FavoriteVideo(
                folder_id=folder.id,
                bvid=bvid,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=None,
            )
        )
        session.add(
            VideoCache(
                bvid=bvid,
                cid=cid,
                title=title,
                description="介绍如何用 AI 做学习复盘",
                owner_name="知识区 UP",
                duration=duration,
                pic_url="https://example.com/cover.jpg",
                content="这是已有的视频摘要内容。",
                content_source="ai_summary",
                outline_json=outline_json,
                subtitle_timeline_json=subtitle_timeline_json,
                page_number=page_number,
                part_title=part_title,
                total_parts=total_parts,
                is_processed=True,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                source_binding_id=None,
            )
        )
        await session.commit()


async def _setup_user_kb_video(client, db_session_factory, email: str):
    auth = await _register_user(client, email, "Video Note Owner")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    kb = await _create_knowledge_base(client, "视频笔记库", headers)
    await _seed_video(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=kb["id"],
    )
    return auth, headers, kb


@pytest.mark.asyncio
async def test_video_notes_require_login(client):
    response = await client.get("/video-notes?knowledge_base_id=1")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_can_create_standard_note_save_list_and_open(
    client, db_session_factory
):
    auth, headers, kb = await _setup_user_kb_video(
        client, db_session_factory, "note-owner@example.com"
    )

    detail_before = await client.get(
        f"/video-notes/{kb['id']}/BVNOTE123",
        headers=headers,
    )
    assert detail_before.status_code == 200
    assert detail_before.json()["note"] is None
    assert detail_before.json()["video"]["title"] == "AI 视频学习法"
    assert detail_before.json()["can_create"] is True

    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BVNOTE123",
            "template_id": "standard",
        },
        headers=headers,
    )
    assert created.status_code == 200
    note = created.json()
    assert note["user_id"] == auth["user"]["id"]
    assert note["workspace_id"] == auth["workspace"]["id"]
    assert note["knowledge_base_id"] == kb["id"]
    assert note["bvid"] == "BVNOTE123"
    assert note["template_id"] == "standard"
    assert note["summary_status"] == "seeded"
    assert "AI 摘要" in [block.get("text") for block in note["blocks"]]
    assert "timestamp_outline" in [block["type"] for block in note["blocks"]]

    updated = await client.put(
        f"/video-notes/{note['id']}",
        json={
            "title": "我的 AI 学习笔记",
            "blocks": [
                {"id": "h1", "type": "heading", "level": 1, "text": "我的 AI 学习笔记"},
                {"id": "p1", "type": "paragraph", "text": "需要复盘提示词。"},
            ],
            "tags": ["AI", "学习"],
            "export_filename_template": "{{title}} - {{bvid}}.md",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "我的 AI 学习笔记"
    assert updated.json()["tags"] == ["AI", "学习"]

    listing = await client.get(
        f"/video-notes?knowledge_base_id={kb['id']}&q=学习&tag=AI",
        headers=headers,
    )
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["bvid"] == "BVNOTE123"
    assert items[0]["folder_title"] == "学习收藏夹"
    assert items[0]["has_note"] is True
    assert items[0]["summary_status"] == "seeded"

    opened = await client.get(
        f"/video-notes/{kb['id']}/BVNOTE123",
        headers=headers,
    )
    assert opened.status_code == 200
    assert opened.json()["note"]["title"] == "我的 AI 学习笔记"


@pytest.mark.asyncio
async def test_video_notes_are_isolated_by_user_and_knowledge_base(
    client, db_session_factory
):
    alice, alice_headers, alice_kb = await _setup_user_kb_video(
        client, db_session_factory, "alice-notes@example.com"
    )
    bob = await _register_user(client, "bob-notes@example.com", "Bob")
    client.cookies.clear()
    bob_headers = {"Authorization": f"Bearer {bob['session_token']}"}

    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": alice_kb["id"],
            "bvid": "BVNOTE123",
            "template_id": "blank",
        },
        headers=alice_headers,
    )
    assert created.status_code == 200

    bob_list = await client.get(
        f"/video-notes?knowledge_base_id={alice_kb['id']}",
        headers=bob_headers,
    )
    assert bob_list.status_code == 404

    bob_update = await client.put(
        f"/video-notes/{created.json()['id']}",
        json={"title": "stolen", "blocks": [], "tags": []},
        headers=bob_headers,
    )
    assert bob_update.status_code == 404

    assert alice["user"]["id"] != bob["user"]["id"]


@pytest.mark.asyncio
async def test_note_body_search_is_opt_in(client, db_session_factory):
    _, headers, kb = await _setup_user_kb_video(
        client, db_session_factory, "body-search@example.com"
    )
    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BVNOTE123",
            "template_id": "blank",
        },
        headers=headers,
    )
    note_id = created.json()["id"]
    await client.put(
        f"/video-notes/{note_id}",
        json={
            "title": "普通标题",
            "blocks": [{"id": "p1", "type": "paragraph", "text": "隐藏检索词"}],
            "tags": [],
        },
        headers=headers,
    )

    default_search = await client.get(
        f"/video-notes?knowledge_base_id={kb['id']}&q=隐藏检索词",
        headers=headers,
    )
    assert default_search.status_code == 200
    assert default_search.json()["items"] == []

    body_search = await client.get(
        f"/video-notes?knowledge_base_id={kb['id']}&q=隐藏检索词&include_body_search=true",
        headers=headers,
    )
    assert body_search.status_code == 200
    assert [item["note_id"] for item in body_search.json()["items"]] == [note_id]


@pytest.mark.asyncio
async def test_markdown_export_uses_frontmatter_blocks_timestamp_links_and_filename(
    client, db_session_factory
):
    _, headers, kb = await _setup_user_kb_video(
        client, db_session_factory, "export-notes@example.com"
    )
    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BVNOTE123",
            "template_id": "blank",
        },
        headers=headers,
    )
    note_id = created.json()["id"]
    await client.put(
        f"/video-notes/{note_id}",
        json={
            "title": "AI/学习:复盘?",
            "blocks": [
                {"id": "h1", "type": "heading", "level": 1, "text": "AI 学习"},
                {
                    "id": "ts1",
                    "type": "timestamp_outline",
                    "items": [{"time": 204, "text": "讲解核心概念"}],
                },
                {"id": "todo1", "type": "todo", "text": "复习这一段", "checked": False},
            ],
            "tags": ["AI", "课程"],
            "export_filename_template": "{{title}} - {{bvid}}.md",
        },
        headers=headers,
    )

    exported = await client.post(
        f"/video-notes/{note_id}/export/markdown",
        headers=headers,
    )

    assert exported.status_code == 200
    payload = exported.json()
    assert payload["filename"] == "AI学习复盘 - BVNOTE123.md"
    assert "bvid: BVNOTE123" in payload["markdown"]
    assert "tags: [AI, 课程]" in payload["markdown"]
    assert (
        "[03:24](https://www.bilibili.com/video/BVNOTE123?t=204)" in payload["markdown"]
    )
    assert "- [ ] 复习这一段" in payload["markdown"]


@pytest.mark.asyncio
async def test_markdown_export_links_multi_part_timestamps_with_page_and_seconds(
    client, db_session_factory
):
    auth = await _register_user(client, "export-multipart-notes@example.com", "Owner")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    kb = await _create_knowledge_base(client, "分P笔记库", headers)
    await _seed_video(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=kb["id"],
        bvid="BV1xx411x7xx",
        cid=222,
        title="合集 P2",
        page_number=2,
        part_title="第二讲",
        total_parts=4,
    )
    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BV1xx411x7xx",
            "template_id": "blank",
        },
        headers=headers,
    )
    note_id = created.json()["id"]
    await client.put(
        f"/video-notes/{note_id}",
        json={
            "title": "分P笔记",
            "blocks": [
                {
                    "id": "ts1",
                    "type": "timestamp_outline",
                    "items": [{"time": 83, "text": "第二讲重点"}],
                },
            ],
            "tags": [],
        },
        headers=headers,
    )

    exported = await client.post(
        f"/video-notes/{note_id}/export/markdown",
        headers=headers,
    )

    assert exported.status_code == 200
    assert (
        "[01:23](https://www.bilibili.com/video/BV1xx411x7xx?p=2&t=83)"
        in exported.json()["markdown"]
    )


@pytest.mark.asyncio
async def test_video_detail_uses_subtitle_timeline_duration_for_legacy_multi_part(
    client, db_session_factory
):
    auth = await _register_user(client, "legacy-part-duration@example.com", "Owner")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    kb = await _create_knowledge_base(client, "旧分P笔记库", headers)
    await _seed_video(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=kb["id"],
        bvid="BVLEGACYPART",
        cid=222,
        title="旧合集 P2",
        duration=3600,
        subtitle_timeline_json=[
            {"from": 0, "to": 12.5, "content": "开场"},
            {"from": 532, "to": 540.2, "content": "结尾"},
        ],
        page_number=2,
        part_title="第二讲",
        total_parts=4,
    )

    detail = await client.get(
        f"/video-notes/{kb['id']}/BVLEGACYPART",
        headers=headers,
    )

    assert detail.status_code == 200
    assert detail.json()["video"]["parts"] == [
        {"page": 2, "cid": 222, "part": "第二讲", "duration": 541}
    ]


@pytest.mark.asyncio
async def test_ai_endpoints_return_suggestions_without_mutating_note(
    client, db_session_factory, monkeypatch
):
    async def missing_llm_credentials(*args, **kwargs):
        raise HTTPException(status_code=400, detail="未配置 LLM API Key")

    monkeypatch.setattr(
        "app.services.video_note_route_ai_runtime.resolve_user_llm_credentials",
        missing_llm_credentials,
    )

    _, headers, kb = await _setup_user_kb_video(
        client, db_session_factory, "ai-notes@example.com"
    )
    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BVNOTE123",
            "template_id": "blank",
        },
        headers=headers,
    )
    note_id = created.json()["id"]

    summary = await client.post(
        f"/video-notes/{note_id}/generate-summary",
        headers=headers,
    )
    assert summary.status_code == 200
    assert summary.json()["tag_suggestions"]
    assert summary.json()["operations"][0]["kind"] == "replace_or_insert_block"

    edit = await client.post(
        f"/video-notes/{note_id}/ai-edit",
        json={
            "action": "generate_questions",
            "instruction": "生成复盘问题",
            "selected_block_ids": [],
        },
        headers=headers,
    )
    assert edit.status_code == 200
    assert edit.json()["operations"][0]["kind"] == "replace_or_insert_block"
    assert edit.json()["operations"][0]["target_block_id"] == "questions"
    question_items = edit.json()["operations"][0]["block"]["items"]
    assert any("介绍学习目标" in item["text"] for item in question_items)
    assert all("生成复盘问题" not in item["text"] for item in question_items)

    timestamps = await client.post(
        f"/video-notes/{note_id}/ai-edit",
        json={
            "action": "generate_timestamps",
            "instruction": "生成时间戳",
            "selected_block_ids": [],
        },
        headers=headers,
    )
    assert timestamps.status_code == 200
    timestamp_operation = timestamps.json()["operations"][0]
    assert timestamp_operation["kind"] == "replace_or_insert_block"
    assert timestamp_operation["target_block_id"] == "timestamp-outline"
    assert timestamp_operation["block"]["type"] == "timestamp_outline"
    assert timestamp_operation["block"]["items"][0]["time"] == 12
    assert any(
        item["text"] == "介绍学习目标" for item in timestamp_operation["block"]["items"]
    )

    async with db_session_factory() as session:
        note = await session.get(VideoNote, note_id)
        assert note.blocks_json == []
        assert note.summary_generated_at is None


@pytest.mark.asyncio
async def test_generate_timestamps_prefers_bilibili_view_points(
    client, db_session_factory, monkeypatch
):
    async def missing_llm_credentials(*args, **kwargs):
        raise AssertionError("official Bilibili chapters should skip LLM fallback")

    async def fake_fetch_bilibili_timestamps(db, *, user, workspace, source):
        assert source.bvid == "BVCHAPTER123"
        assert source.cid == 456
        return [
            {"time": 34, "text": "官方章节：问题背景"},
            {"time": 126, "text": "官方章节：操作步骤"},
        ]

    monkeypatch.setattr(
        "app.services.video_note_route_ai_runtime.resolve_user_llm_credentials",
        missing_llm_credentials,
    )
    monkeypatch.setattr(
        "app.services.video_note_route_ai_runtime.fetch_bilibili_view_point_timestamps",
        fake_fetch_bilibili_timestamps,
    )

    auth = await _register_user(client, "ai-bilibili-chapters@example.com", "Owner")
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}
    kb = await _create_knowledge_base(client, "章节笔记库", headers)
    await _seed_video(
        db_session_factory,
        workspace_id=auth["workspace"]["id"],
        knowledge_base_id=kb["id"],
        bvid="BVCHAPTER123",
        cid=456,
        outline_json=[],
    )
    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BVCHAPTER123",
            "template_id": "blank",
        },
        headers=headers,
    )
    note_id = created.json()["id"]

    timestamps = await client.post(
        f"/video-notes/{note_id}/ai-edit",
        json={
            "action": "generate_timestamps",
            "instruction": "生成时间戳",
            "selected_block_ids": [],
        },
        headers=headers,
    )

    assert timestamps.status_code == 200
    payload = timestamps.json()
    assert payload["result_source"] == "official"
    assert payload["message"] == "✓ 已根据 B 站官方章节生成时间戳提纲"
    assert payload["operations"][0]["block"]["items"] == [
        {"time": 34, "text": "官方章节：问题背景"},
        {"time": 126, "text": "官方章节：操作步骤"},
    ]


@pytest.mark.asyncio
async def test_ai_endpoints_use_model_generated_structured_content(
    client, db_session_factory, monkeypatch
):
    _, headers, kb = await _setup_user_kb_video(
        client, db_session_factory, "ai-model-notes@example.com"
    )
    created = await client.post(
        "/video-notes",
        json={
            "knowledge_base_id": kb["id"],
            "bvid": "BVNOTE123",
            "template_id": "blank",
        },
        headers=headers,
    )
    note_id = created.json()["id"]
    calls: list[list[dict]] = []

    async def fake_generate_video_note_ai_json(messages, llm_config, get_llm_client):
        calls.append(messages)
        user_prompt = messages[-1]["content"]
        if "复盘问题" in user_prompt:
            return {
                "questions": [
                    "AI 学习复盘如何形成闭环？",
                    "视频中的学习目标可以怎样迁移到我的项目？",
                ]
            }
        if "时间戳" in user_prompt:
            return {
                "timestamps": [
                    {"time": 24, "text": "开场说明学习目标"},
                    {"time": 86, "text": "拆解复盘流程"},
                ]
            }
        return {
            "summary": "模型生成的摘要强调先提炼目标，再用问题驱动复盘。",
            "key_points": ["建立复盘闭环", "把结论转为下一步行动"],
            "tags": ["AI", "复盘"],
        }

    async def fake_resolve_user_llm_credentials(*args, **kwargs):
        return SimpleNamespace(
            to_llm_config=lambda: {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "api_key": "fake-key",
                "base_url": "https://example.com/v1",
                "thinking_config": {},
            }
        )

    monkeypatch.setattr(
        "app.services.video_note_route_ai_runtime.resolve_user_llm_credentials",
        fake_resolve_user_llm_credentials,
    )
    monkeypatch.setattr(
        "app.services.video_note_route_ai_runtime.generate_video_note_ai_json",
        fake_generate_video_note_ai_json,
    )

    summary = await client.post(
        f"/video-notes/{note_id}/generate-summary",
        headers=headers,
    )
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["result_source"] == "ai"
    assert summary_payload["operations"][0]["block"]["text"] == (
        "模型生成的摘要强调先提炼目标，再用问题驱动复盘。"
    )
    assert summary_payload["operations"][1]["block"]["items"] == [
        {"text": "建立复盘闭环"},
        {"text": "把结论转为下一步行动"},
    ]
    assert summary_payload["tag_suggestions"] == ["AI", "复盘"]

    # 摘要生成成功后，笔记的 summary_status 应同步更新
    detail = await client.get(
        f"/video-notes/{kb['id']}/BVNOTE123",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["note"]["summary_status"] == "generated"
    assert detail.json()["note"]["summary_generated_at"] is not None

    questions = await client.post(
        f"/video-notes/{note_id}/ai-edit",
        json={
            "action": "generate_questions",
            "instruction": "生成复盘问题",
            "selected_block_ids": [],
        },
        headers=headers,
    )
    assert questions.status_code == 200
    assert questions.json()["operations"][0]["target_block_id"] == "questions"
    question_items = questions.json()["operations"][0]["block"]["items"]
    assert question_items == [
        {"text": "AI 学习复盘如何形成闭环？"},
        {"text": "视频中的学习目标可以怎样迁移到我的项目？"},
    ]
    assert all("生成复盘问题" not in item["text"] for item in question_items)

    timestamps = await client.post(
        f"/video-notes/{note_id}/ai-edit",
        json={
            "action": "generate_timestamps",
            "instruction": "生成时间戳",
            "selected_block_ids": [],
        },
        headers=headers,
    )
    assert timestamps.status_code == 200
    timestamp_items = timestamps.json()["operations"][0]["block"]["items"]
    assert timestamp_items == [
        {"time": 24, "text": "开场说明学习目标"},
        {"time": 86, "text": "拆解复盘流程"},
    ]

    assert len(calls) == 3
    assert all(call[0]["role"] == "system" for call in calls)
