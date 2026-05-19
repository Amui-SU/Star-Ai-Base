from contextlib import asynccontextmanager
import unittest

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, UserSession as UserSessionModel
from app.routers import auth


class AuthSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.original_get_db_context = auth.get_db_context
        auth.login_sessions.clear()

        @asynccontextmanager
        async def test_db_context():
            async with self.session_factory() as session:
                yield session

        auth.get_db_context = test_db_context

    async def asyncTearDown(self) -> None:
        auth.get_db_context = self.original_get_db_context
        auth.login_sessions.clear()
        await self.engine.dispose()

    async def add_session(self, session_id: str, is_valid: bool = True) -> None:
        async with self.session_factory() as db:
            db.add(
                UserSessionModel(
                    session_id=session_id,
                    bili_mid=123,
                    bili_uname="tester",
                    sessdata="sess",
                    bili_jct="csrf",
                    dedeuserid="123",
                    is_valid=is_valid,
                )
            )
            await db.commit()

    async def test_get_session_rejects_cached_revoked_session(self) -> None:
        await self.add_session("revoked", is_valid=False)
        auth.login_sessions["revoked"] = {
            "cookies": {"SESSDATA": "sess", "bili_jct": "csrf", "DedeUserID": "123"},
            "user_info": {"mid": 123, "uname": "tester"},
        }

        session = await auth.get_session("revoked")

        self.assertIsNone(session)
        self.assertNotIn("revoked", auth.login_sessions)

    async def test_logout_marks_persisted_session_invalid(self) -> None:
        await self.add_session("active", is_valid=True)
        auth.login_sessions["active"] = {
            "cookies": {"SESSDATA": "sess", "bili_jct": "csrf", "DedeUserID": "123"},
            "user_info": {"mid": 123, "uname": "tester"},
        }

        async with self.session_factory() as db:
            response = await auth.logout("active", db)

        async with self.session_factory() as db:
            result = await db.execute(
                select(UserSessionModel).where(UserSessionModel.session_id == "active")
            )
            stored_session = result.scalar_one()

        self.assertEqual(response, {"message": "已退出登录"})
        self.assertFalse(stored_session.is_valid)
        self.assertNotIn("active", auth.login_sessions)


if __name__ == "__main__":
    unittest.main()
