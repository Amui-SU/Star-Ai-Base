"""
AI时间戳功能手动验证脚本

用于验证分P视频导入后，数据库中是否正确保存了：
1. 分P元信息（page_number, part_title, total_parts）
2. 字幕时间轴数据（subtitle_timeline_json）
"""

import asyncio
from sqlalchemy import select
from app.database import get_db_context
from app.models import VideoCache


async def show_ai_timestamp_data():
    """显示AI时间戳数据是否正确保存"""

    async with get_db_context() as db:
        # 查询最近导入的视频（包含分P信息的）
        result = await db.execute(
            select(VideoCache)
            .where(VideoCache.page_number.isnot(None))
            .order_by(VideoCache.created_at.desc())
            .limit(5)
        )
        videos = result.scalars().all()

        if not videos:
            print("❌ 未找到包含分P信息的视频")
            print("提示：请先使用 /imports/multi-part 接口导入一个分P视频")
            return

        print(f"✅ 找到 {len(videos)} 个包含分P信息的视频\n")

        for video in videos:
            print(f"视频标题: {video.title}")
            print(f"  BVID: {video.bvid}")
            print(f"  CID: {video.cid}")
            print(f"  分P编号: {video.page_number}/{video.total_parts}")
            print(f"  分P标题: {video.part_title}")

            if video.subtitle_timeline_json:
                timeline = video.subtitle_timeline_json
                print(f"  字幕时间轴: {len(timeline)} 条")
                if timeline:
                    first = timeline[0]
                    print(
                        f"    首条: {first.get('from')}s - {first.get('to')}s: {first.get('content')[:30]}..."
                    )
            else:
                print(f"  字幕时间轴: 无")

            if video.outline_json:
                outline = video.outline_json
                print(f"  AI提纲: {len(outline)} 段")
            else:
                print(f"  AI提纲: 无")

            print()


async def show_subtitle_timeline_structure():
    """显示字幕时间轴数据结构"""

    async with get_db_context() as db:
        result = await db.execute(
            select(VideoCache)
            .where(VideoCache.subtitle_timeline_json.isnot(None))
            .limit(1)
        )
        video = result.scalar_one_or_none()

        if not video:
            print("❌ 未找到包含字幕时间轴的视频")
            return

        timeline = video.subtitle_timeline_json
        print(f"✅ 字幕时间轴数据结构验证")
        print(f"  视频: {video.title}")
        print(f"  时间轴条目数: {len(timeline)}")

        # 验证数据结构
        if timeline:
            first = timeline[0]
            required_keys = ["from", "to", "content"]
            missing_keys = [key for key in required_keys if key not in first]

            if missing_keys:
                print(f"  ❌ 缺少必需字段: {missing_keys}")
            else:
                print(f"  ✅ 数据结构正确")
                print(f"  示例数据:")
                print(f"    开始时间: {first['from']}s")
                print(f"    结束时间: {first['to']}s")
                print(f"    内容: {first['content'][:50]}")


async def main():
    print("=" * 60)
    print("AI时间戳功能数据验证")
    print("=" * 60)
    print()

    await show_ai_timestamp_data()
    print("\n" + "=" * 60 + "\n")
    await show_subtitle_timeline_structure()


if __name__ == "__main__":
    asyncio.run(main())
