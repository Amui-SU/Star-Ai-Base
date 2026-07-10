-- 数据库迁移：为AI时间戳功能添加字段
-- 执行时间：根据项目需要
-- 说明：所有新字段都是可空的，向后兼容现有数据

-- 为 video_cache 表添加分P元信息和时间轴字段
ALTER TABLE video_cache
ADD COLUMN page_number INTEGER,
ADD COLUMN part_title VARCHAR(500),
ADD COLUMN total_parts INTEGER,
ADD COLUMN subtitle_timeline_json JSON;

-- 注释说明
COMMENT ON COLUMN video_cache.page_number IS '分P编号（1, 2, 3...），用于AI时间戳功能';
COMMENT ON COLUMN video_cache.part_title IS '分P原始标题，用于AI时间戳功能';
COMMENT ON COLUMN video_cache.total_parts IS '总分P数，用于AI时间戳功能';
COMMENT ON COLUMN video_cache.subtitle_timeline_json IS '完整字幕时间轴数据，格式: [{"from": 0.0, "to": 3.5, "content": "文本"}]';

-- 可选：为单P视频补充默认值（如果需要）
-- UPDATE video_cache
-- SET page_number = 1, total_parts = 1
-- WHERE page_number IS NULL AND cid IS NOT NULL;
