from datetime import datetime

import pytest
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
    title: str = "AI 视频学习法",
    folder_title: str = "学习收藏夹",
):
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
                title=title,
                description="介绍如何用 AI 做学习复盘",
                owner_name="知识区 UP",
                duration=360,
                pic_url="https://example.com/cover.jpg",
                content="这是已有的视频摘要内容。",
                content_source="ai_summary",
                outline_json=[
                    {
                        "title": "开场",
                        "timestamp": 12,
                        "points": [{"content": "介绍学习目标", "timestamp": 24}],
                    }
                ],
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
async def test_ai_endpoints_return_suggestions_without_mutating_note(
    client, db_session_factory
):
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
    assert edit.json()["operations"][0]["kind"] == "insert_block"
    question_items = edit.json()["operations"][0]["block"]["items"]
    assert any("介绍学习目标" in item["text"] for item in question_items)

    async with db_session_factory() as session:
        note = await session.get(VideoNote, note_id)
        assert note.blocks_json == []
        assert note.summary_generated_at is None
