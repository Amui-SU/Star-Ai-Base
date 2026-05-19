import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import knowledge


class DummyRagService:
    def __init__(self) -> None:
        self.cleared = False
        self.deleted_bvids: list[str] = []

    def clear_collection(self) -> None:
        self.cleared = True

    def delete_video(self, bvid: str) -> None:
        self.deleted_bvids.append(bvid)


class KnowledgeAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_get_session = knowledge.get_session
        self.original_get_rag_service = knowledge.get_rag_service
        self.rag = DummyRagService()
        knowledge.get_rag_service = lambda: self.rag

        app = FastAPI()
        app.include_router(knowledge.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        knowledge.get_session = self.original_get_session
        knowledge.get_rag_service = self.original_get_rag_service

    def set_session(self, session: dict | None) -> None:
        async def fake_get_session(session_id: str) -> dict | None:
            return session

        knowledge.get_session = fake_get_session

    def test_clear_requires_valid_session(self) -> None:
        self.set_session(None)

        response = self.client.delete("/knowledge/clear?session_id=invalid")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.rag.cleared)

    def test_delete_video_requires_valid_session(self) -> None:
        self.set_session(None)

        response = self.client.delete("/knowledge/video/BV1xx411c7mD?session_id=invalid")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.rag.deleted_bvids, [])

    def test_destructive_routes_allow_valid_session(self) -> None:
        self.set_session({
            "cookies": {"SESSDATA": "sess", "bili_jct": "csrf", "DedeUserID": "123"},
            "user_info": {"mid": 123, "uname": "tester"},
        })

        clear_response = self.client.delete("/knowledge/clear?session_id=valid")
        delete_response = self.client.delete("/knowledge/video/BV1xx411c7mD?session_id=valid")

        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(self.rag.cleared)
        self.assertEqual(self.rag.deleted_bvids, ["BV1xx411c7mD"])


if __name__ == "__main__":
    unittest.main()
