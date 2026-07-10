"""
前后端分P视频适配手动验证脚本

验证后端是否正确返回分P信息，供前端使用
"""

import asyncio
from sqlalchemy import select
from app.database import get_db_context
from app.models import VideoCache
from app.services.video_note_presenters import (
    VideoNoteSource,
    video_to_response,
)


async def verify_backend_returns_parts():
    """验证后端是否正确返回分P信息"""

    async with get_db_context() as db:
        # 查询一个分P视频
        result = await db.execute(
            select(VideoCache)
            .where(VideoCache.page_number.isnot(None))
            .where(VideoCache.total_parts > 1)
            .limit(1)
        )
        video = result.scalar_one_or_none()

        if not video:
            print("❌ 未找到分P视频，请先导入一个分P视频")
            print("\n提示：使用以下命令导入分P视频：")
            print("POST /imports/multi-part")
            return

        print(f"✅ 找到分P视频: {video.title}")
        print(f"  BVID: {video.bvid}")
        print(f"  分P信息: P{video.page_number}/{video.total_parts}")
        print()

        # 模拟构建 VideoNoteSource
        source = VideoNoteSource(
            bvid=video.bvid,
            cid=video.cid,
            title=video.title,
            original_title=video.title,
            folder_title="测试收藏夹",
            owner_name=video.owner_name,
            duration=video.duration,
            pic_url=video.pic_url,
            description=video.description,
            source_binding_id=None,
            content=video.content,
            outline=video.outline_json,
            owner_mid=video.owner_mid,
            page_number=video.page_number,
            part_title=video.part_title,
            total_parts=video.total_parts,
        )

        # 验证 video_to_response
        response = video_to_response(source)

        print("=== 后端返回的数据结构 ===")
        print(f"bvid: {response['bvid']}")
        print(f"title: {response['title']}")
        print(f"url: {response['url']}")

        if response.get("parts"):
            print(f"\n✅ parts 字段存在:")
            for part in response["parts"]:
                print(f"  - P{part['page']}: {part['part']}")
                print(f"    CID: {part['cid']}")
                print(f"    时长: {part['duration']}秒")
        else:
            print(f"\n❌ parts 字段缺失（应该有但没返回）")

        print("\n=== 前端期望的数据结构 ===")
        print(
            """
interface VideoNoteVideo {
  bvid: string;
  title: string;
  url: string;
  parts?: VideoNotePart[] | null;  // 前端期望这个字段
}

interface VideoNotePart {
  page: number;    // 分P编号
  cid: number;     // CID
  part: string;    // 分P标题
  duration: number; // 时长
}
        """
        )

        # 验证数据结构完整性
        print("\n=== 数据结构验证 ===")
        issues = []

        if not response.get("parts"):
            issues.append("缺少 parts 字段")
        elif not isinstance(response["parts"], list):
            issues.append("parts 应该是数组")
        else:
            for i, part in enumerate(response["parts"]):
                if "page" not in part:
                    issues.append(f"parts[{i}] 缺少 page 字段")
                if "cid" not in part:
                    issues.append(f"parts[{i}] 缺少 cid 字段")
                if "part" not in part:
                    issues.append(f"parts[{i}] 缺少 part 字段")
                if "duration" not in part:
                    issues.append(f"parts[{i}] 缺少 duration 字段")

        if issues:
            print("❌ 发现问题:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ 数据结构完整，前后端适配正常！")


async def verify_single_part_video():
    """验证单P视频的处理"""

    async with get_db_context() as db:
        result = await db.execute(
            select(VideoCache).where(VideoCache.page_number.is_(None)).limit(1)
        )
        video = result.scalar_one_or_none()

        if not video:
            print("未找到单P视频")
            return

        print(f"\n=== 单P视频测试 ===")
        print(f"视频: {video.title}")

        source = VideoNoteSource(
            bvid=video.bvid,
            cid=video.cid,
            title=video.title,
            original_title=video.title,
            folder_title="测试",
            owner_name=video.owner_name,
            duration=video.duration,
            pic_url=video.pic_url,
            description=video.description,
            source_binding_id=None,
            content=video.content,
            outline=video.outline_json,
            owner_mid=video.owner_mid,
            page_number=video.page_number,
            part_title=video.part_title,
            total_parts=video.total_parts,
        )

        response = video_to_response(source)

        if response.get("parts") is None:
            print("✅ 单P视频正确返回 parts=None")
        else:
            print(f"⚠️ 单P视频返回了 parts={response['parts']}")


async def main():
    print("=" * 60)
    print("前后端分P视频适配测试")
    print("=" * 60)
    print()

    await verify_backend_returns_parts()
    await verify_single_part_video()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
