import os
import tempfile
import unittest
from pathlib import Path

_DB_DIR = tempfile.mkdtemp(prefix="bilibili-rag-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_DB_DIR) / 'test.db'}"

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.database import async_session_factory, init_db
from app.models import FavoriteFolder, FavoriteVideo, UserSession
from app.routers import auth, chat


class FrontendApiClientTests(unittest.TestCase):
    def test_frontend_api_client_file_exports_required_clients(self):
        api_client = Path(__file__).resolve().parents[1] / "frontend" / "lib" / "api.ts"

        self.assertTrue(api_client.exists(), "frontend/lib/api.ts must exist for @/lib/api imports")
        content = api_client.read_text(encoding="utf-8")

        for export_name in ("authApi", "favoritesApi", "knowledgeApi", "chatApi", "API_BASE_URL"):
            self.assertIn(f"export const {export_name}", content)


class CriticalSecurityRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        auth.login_sessions.clear()
        async with async_session_factory() as db:
            for model in (FavoriteVideo, FavoriteFolder, UserSession):
                await db.execute(delete(model))
            await db.commit()

    async def _create_session(self, session_id: str, mid: int = 1001) -> None:
        async with async_session_factory() as db:
            db.add(
                UserSession(
                    session_id=session_id,
                    bili_mid=mid,
                    bili_uname=f"user-{mid}",
                    sessdata="sess",
                    bili_jct="csrf",
                    dedeuserid=str(mid),
                    is_valid=True,
                )
            )
            await db.commit()

    async def test_logout_invalidates_persisted_session(self):
        await self._create_session("session-to-revoke")

        async with async_session_factory() as db:
            await auth.logout("session-to-revoke", db)

        self.assertIsNone(await auth.get_session("session-to-revoke"))
        async with async_session_factory() as db:
            is_valid = await db.scalar(
                select(UserSession.is_valid).where(UserSession.session_id == "session-to-revoke")
            )
        self.assertFalse(is_valid)

    async def test_llm_provider_config_requires_valid_session_before_writing_env(self):
        env_file = Path(_DB_DIR) / ".env.local"
        original_env_file_path = chat._env_file_path
        original_provider = chat._current_llm_provider
        original_native_key = chat.settings.openai_native_api_key
        original_native_base_url = chat.settings.openai_native_base_url

        chat._env_file_path = lambda: env_file
        try:
            body = chat.LLMProviderConfigRequest(
                provider="openai",
                api_key="attacker-key",
                base_url="https://attacker.example/v1",
            )

            with self.assertRaises(HTTPException) as raised:
                await chat.save_llm_provider_config(body)

            self.assertEqual(raised.exception.status_code, 401)
            self.assertFalse(env_file.exists(), "unauthenticated config writes must not persist secrets")
        finally:
            chat._env_file_path = original_env_file_path
            chat._current_llm_provider = original_provider
            chat.settings.openai_native_api_key = original_native_key
            chat.settings.openai_native_base_url = original_native_base_url

    async def test_chat_search_scopes_vector_query_to_session_videos(self):
        await self._create_session("search-session", mid=2002)
        async with async_session_factory() as db:
            folder = FavoriteFolder(
                session_id="search-session",
                media_id=42,
                title="Private folder",
                media_count=1,
                is_selected=True,
            )
            db.add(folder)
            await db.flush()
            db.add(FavoriteVideo(folder_id=folder.id, bvid="BV_ALLOWED", is_selected=True))
            await db.commit()

        class FakeRag:
            def __init__(self):
                self.calls = []

            def search(self, query, k=5, bvids=None):
                self.calls.append({"query": query, "k": k, "bvids": bvids})
                return [
                    type(
                        "Doc",
                        (),
                        {
                            "metadata": {"bvid": "BV_ALLOWED", "title": "Allowed", "url": ""},
                            "page_content": "allowed private content",
                        },
                    )()
                ]

        fake_rag = FakeRag()
        original_get_rag_service = chat.get_rag_service
        chat.get_rag_service = lambda: fake_rag
        try:
            async with async_session_factory() as db:
                response = await chat.search_videos(
                    "private topic",
                    k=3,
                    session_id="search-session",
                    db=db,
                )

            self.assertEqual(response["results"][0]["bvid"], "BV_ALLOWED")
            self.assertEqual(fake_rag.calls, [{"query": "private topic", "k": 3, "bvids": ["BV_ALLOWED"]}])
        finally:
            chat.get_rag_service = original_get_rag_service
