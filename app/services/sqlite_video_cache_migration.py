"""SQLite video_cache migration helpers."""

from sqlalchemy.engine import Connection

from app.services.sqlite_schema_inspection import (
    quote_sqlite_identifier,
    sqlite_has_unique_bvid_index,
    sqlite_select_expr,
    sqlite_table_columns,
)


def sqlite_rebuild_video_cache_without_unique_bvid(sync_conn: Connection) -> None:
    existing = sqlite_table_columns(sync_conn, "video_cache")
    if not existing or not sqlite_has_unique_bvid_index(sync_conn):
        return

    sync_conn.exec_driver_sql('DROP TABLE IF EXISTS "video_cache_new"')
    sync_conn.exec_driver_sql(
        """
        CREATE TABLE "video_cache_new" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bvid VARCHAR(20) NOT NULL,
            cid INTEGER,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            owner_name VARCHAR(100),
            owner_mid INTEGER,
            content TEXT,
            content_source VARCHAR(20),
            outline_json JSON,
            duration INTEGER,
            pic_url VARCHAR(500),
            page_number INTEGER,
            part_title VARCHAR(500),
            total_parts INTEGER,
            subtitle_timeline_json JSON,
            is_processed BOOLEAN,
            process_error TEXT,
            workspace_id INTEGER,
            knowledge_base_id INTEGER,
            source_binding_id INTEGER,
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )

    columns = [
        "id",
        "bvid",
        "cid",
        "title",
        "description",
        "owner_name",
        "owner_mid",
        "content",
        "content_source",
        "outline_json",
        "duration",
        "pic_url",
        "page_number",
        "part_title",
        "total_parts",
        "subtitle_timeline_json",
        "is_processed",
        "process_error",
        "workspace_id",
        "knowledge_base_id",
        "source_binding_id",
        "created_at",
        "updated_at",
    ]
    expressions = [
        sqlite_select_expr(existing, "id"),
        sqlite_select_expr(existing, "bvid"),
        sqlite_select_expr(existing, "cid"),
        sqlite_select_expr(existing, "title", "COALESCE(bvid, '')"),
        sqlite_select_expr(existing, "description"),
        sqlite_select_expr(existing, "owner_name"),
        sqlite_select_expr(existing, "owner_mid"),
        sqlite_select_expr(existing, "content"),
        sqlite_select_expr(existing, "content_source"),
        sqlite_select_expr(existing, "outline_json"),
        sqlite_select_expr(existing, "duration"),
        sqlite_select_expr(existing, "pic_url"),
        sqlite_select_expr(existing, "page_number"),
        sqlite_select_expr(existing, "part_title"),
        sqlite_select_expr(existing, "total_parts"),
        sqlite_select_expr(existing, "subtitle_timeline_json"),
        sqlite_select_expr(existing, "is_processed", "0"),
        sqlite_select_expr(existing, "process_error"),
        sqlite_select_expr(existing, "workspace_id"),
        sqlite_select_expr(existing, "knowledge_base_id"),
        sqlite_select_expr(existing, "source_binding_id"),
        sqlite_select_expr(existing, "created_at", "CURRENT_TIMESTAMP"),
        sqlite_select_expr(existing, "updated_at", "CURRENT_TIMESTAMP"),
    ]
    sync_conn.exec_driver_sql(
        f"""
        INSERT INTO "video_cache_new" ({", ".join(quote_sqlite_identifier(c) for c in columns)})
        SELECT {", ".join(expressions)}
        FROM "video_cache"
        """
    )
    sync_conn.exec_driver_sql('DROP TABLE "video_cache"')
    sync_conn.exec_driver_sql('ALTER TABLE "video_cache_new" RENAME TO "video_cache"')


def sqlite_create_video_cache_indexes(sync_conn: Connection) -> None:
    if not sqlite_table_columns(sync_conn, "video_cache"):
        return
    sync_conn.exec_driver_sql(
        'CREATE INDEX IF NOT EXISTS "ix_video_cache_bvid" ON "video_cache" ("bvid")'
    )
    sync_conn.exec_driver_sql(
        'CREATE INDEX IF NOT EXISTS "ix_video_cache_workspace_id" '
        'ON "video_cache" ("workspace_id")'
    )
    sync_conn.exec_driver_sql(
        'CREATE INDEX IF NOT EXISTS "ix_video_cache_knowledge_base_id" '
        'ON "video_cache" ("knowledge_base_id")'
    )
    sync_conn.exec_driver_sql(
        'CREATE INDEX IF NOT EXISTS "ix_video_cache_source_binding_id" '
        'ON "video_cache" ("source_binding_id")'
    )
    sync_conn.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS "ix_video_cache_scope_bvid"
        ON "video_cache" (
            "workspace_id",
            "knowledge_base_id",
            COALESCE("source_binding_id", -1),
            "bvid"
        )
        WHERE "workspace_id" IS NOT NULL
          AND "knowledge_base_id" IS NOT NULL
        """
    )


def sqlite_clone_scoped_video_cache_rows(sync_conn: Connection) -> None:
    existing_video_cache_columns = sqlite_table_columns(sync_conn, "video_cache")
    if not existing_video_cache_columns or not sqlite_table_columns(
        sync_conn, "favorite_videos"
    ):
        return
    optional_part_columns = [
        "page_number",
        "part_title",
        "total_parts",
        "subtitle_timeline_json",
    ]
    available_part_columns = [
        column
        for column in optional_part_columns
        if column in existing_video_cache_columns
    ]
    insert_part_columns = "".join(
        f"            {quote_sqlite_identifier(column)},\n"
        for column in available_part_columns
    )
    select_part_columns = "".join(
        f"            src.{quote_sqlite_identifier(column)},\n"
        for column in available_part_columns
    )
    sync_conn.exec_driver_sql(
        f"""
        WITH desired AS (
            SELECT
                fv.bvid AS bvid,
                fv.workspace_id AS workspace_id,
                fv.knowledge_base_id AS knowledge_base_id,
                fv.source_binding_id AS source_binding_id
            FROM favorite_videos fv
            WHERE fv.workspace_id IS NOT NULL
              AND fv.knowledge_base_id IS NOT NULL
            GROUP BY
                fv.bvid,
                fv.workspace_id,
                fv.knowledge_base_id,
                COALESCE(fv.source_binding_id, -1)
        ),
        source AS (
            SELECT
                desired.bvid AS bvid,
                desired.workspace_id AS workspace_id,
                desired.knowledge_base_id AS knowledge_base_id,
                desired.source_binding_id AS source_binding_id,
                COALESCE(
                    MIN(
                        CASE
                            WHEN src.workspace_id = desired.workspace_id
                             AND src.knowledge_base_id = desired.knowledge_base_id
                             AND COALESCE(src.source_binding_id, -1) =
                                 COALESCE(desired.source_binding_id, -1)
                            THEN src.id
                        END
                    ),
                    MIN(src.id)
                ) AS source_cache_id
            FROM desired
            JOIN video_cache src
              ON src.bvid = desired.bvid
            GROUP BY
                desired.bvid,
                desired.workspace_id,
                desired.knowledge_base_id,
                COALESCE(desired.source_binding_id, -1)
        )
        INSERT INTO video_cache (
            bvid,
            cid,
            title,
            description,
            owner_name,
            owner_mid,
            content,
            content_source,
            outline_json,
            duration,
            pic_url,
{insert_part_columns}            is_processed,
            process_error,
            workspace_id,
            knowledge_base_id,
            source_binding_id,
            created_at,
            updated_at
        )
        SELECT
            src.bvid,
            src.cid,
            src.title,
            src.description,
            src.owner_name,
            src.owner_mid,
            src.content,
            src.content_source,
            src.outline_json,
            src.duration,
            src.pic_url,
{select_part_columns}            src.is_processed,
            src.process_error,
            source.workspace_id,
            source.knowledge_base_id,
            source.source_binding_id,
            src.created_at,
            src.updated_at
        FROM source
        JOIN video_cache src
          ON src.id = source.source_cache_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM video_cache vc
            WHERE vc.bvid = source.bvid
              AND vc.workspace_id = source.workspace_id
              AND vc.knowledge_base_id = source.knowledge_base_id
              AND COALESCE(vc.source_binding_id, -1) =
                  COALESCE(source.source_binding_id, -1)
        )
        """
    )
