from app.models import Base
from app.models import FavoriteFolder
from app.models import FavoriteVideo
from app.models import IngestionTask
from app.models import VideoCache
from app.models import VideoTitleOverride
from app.models_content import FavoriteFolder as FocusedFavoriteFolder
from app.models_content import FavoriteVideo as FocusedFavoriteVideo
from app.models_content import IngestionTask as FocusedIngestionTask
from app.models_content import VideoCache as FocusedVideoCache
from app.models_content import VideoTitleOverride as FocusedVideoTitleOverride


def test_content_ingestion_models_keep_legacy_app_models_exports():
    assert VideoCache is FocusedVideoCache
    assert FavoriteFolder is FocusedFavoriteFolder
    assert FavoriteVideo is FocusedFavoriteVideo
    assert VideoTitleOverride is FocusedVideoTitleOverride
    assert IngestionTask is FocusedIngestionTask


def test_content_ingestion_models_share_declarative_base_metadata():
    expected_tables = {
        "video_cache": VideoCache,
        "favorite_folders": FavoriteFolder,
        "favorite_videos": FavoriteVideo,
        "video_title_overrides": VideoTitleOverride,
        "ingestion_tasks": IngestionTask,
    }

    for table_name, model_class in expected_tables.items():
        assert model_class.__table__ is Base.metadata.tables[table_name]
