"""Shared SQLAlchemy declarative base for ORM model modules."""

from datetime import datetime

from sqlalchemy.orm import declarative_base

from app.time_utils import utc_now


def _utc_now() -> datetime:
    """返回 aware UTC 时间（替代已弃用的 datetime.utcnow）"""
    return utc_now()


Base = declarative_base()
