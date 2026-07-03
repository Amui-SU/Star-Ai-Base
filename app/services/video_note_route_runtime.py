"""Route orchestration facade for video note endpoints."""

from app.services.video_note_route_ai_runtime import (
    edit_video_note_with_ai_from_router,
    generate_video_note_summary_from_router,
)
from app.services.video_note_route_export_runtime import (
    export_video_note_markdown_from_router,
)
from app.services.video_note_route_mutation_runtime import (
    create_video_note_from_router,
    update_video_note_from_router,
)
from app.services.video_note_route_query_runtime import (
    get_video_note_detail_from_router,
    list_video_notes_from_router,
)

__all__ = [
    "create_video_note_from_router",
    "edit_video_note_with_ai_from_router",
    "export_video_note_markdown_from_router",
    "generate_video_note_summary_from_router",
    "get_video_note_detail_from_router",
    "list_video_notes_from_router",
    "update_video_note_from_router",
]
