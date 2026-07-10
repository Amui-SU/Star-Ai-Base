"""B站分P视频处理辅助函数"""

from typing import Any


def detect_multi_part_video(video_info: dict[str, Any]) -> dict[str, Any]:
    """
    检测是否为分P视频并提取分P信息

    Returns:
        {
            "is_multi_part": bool,
            "total_parts": int,
            "pages": list[dict],  # 分P列表
            "default_cid": int,
        }
    """
    pages = video_info.get("pages", [])
    videos = video_info.get("videos", 1)

    is_multi_part = videos > 1 or len(pages) > 1

    return {
        "is_multi_part": is_multi_part,
        "total_parts": len(pages) if pages else 1,
        "pages": pages,
        "default_cid": video_info.get("cid"),
    }


def format_part_title(
    base_title: str,
    page_num: int,
    part_title: str | None = None,
    total: int = 1,
) -> str:
    """
    格式化分P视频标题

    Args:
        base_title: 视频基础标题
        page_num: 分P编号（从1开始）
        part_title: 分P自定义标题
        total: 总分P数

    Returns:
        格式化后的标题

    Examples:
        >>> format_part_title("教程合集", 1, "基础入门", 3)
        "教程合集 P1/3: 基础入门"
        >>> format_part_title("教程合集", 2, None, 3)
        "教程合集 P2/3"
    """
    if total <= 1:
        return base_title

    part_info = f"P{page_num}/{total}"

    if part_title and part_title.strip() and part_title != base_title:
        return f"{base_title} {part_info}: {part_title.strip()}"

    return f"{base_title} {part_info}"


def extract_page_info(page_data: dict[str, Any]) -> dict[str, Any]:
    """
    提取单个分P的信息

    Returns:
        {
            "cid": int,
            "page": int,
            "part": str,
            "duration": int,
        }
    """
    return {
        "cid": page_data.get("cid"),
        "page": page_data.get("page", 1),
        "part": page_data.get("part", ""),
        "duration": page_data.get("duration", 0),
    }


def validate_page_selection(
    page_indices: list[int], total_parts: int, allow_empty: bool = False
) -> tuple[bool, str]:
    """
    验证用户选择的分P是否有效

    Args:
        page_indices: 用户选择的分P索引列表（从1开始）
        total_parts: 总分P数
        allow_empty: 是否允许空选择（空=全部）

    Returns:
        (是否有效, 错误消息)
    """
    if not page_indices:
        if allow_empty:
            return True, ""
        return False, "未选择任何分P"

    if not all(isinstance(i, int) for i in page_indices):
        return False, "分P索引必须为整数"

    if any(i < 1 or i > total_parts for i in page_indices):
        return False, f"分P索引超出范围（1-{total_parts}）"

    if len(set(page_indices)) != len(page_indices):
        return False, "存在重复的分P索引"

    return True, ""


def build_import_summary(
    base_title: str, selected_pages: list[dict[str, Any]], total_parts: int
) -> str:
    """
    构建导入摘要信息

    Returns:
        摘要字符串，如："将导入《教程合集》的 3 个分P（共 3 个）"
    """
    selected_count = len(selected_pages)

    if selected_count == total_parts:
        return f"将导入《{base_title}》的全部 {total_parts} 个分P"
    elif selected_count == 1:
        page = selected_pages[0]
        part_title = page.get("part", "")
        if part_title:
            return f"将导入《{base_title}》P{page['page']}: {part_title}"
        return f"将导入《{base_title}》P{page['page']}"
    else:
        page_nums = ", ".join(f"P{p['page']}" for p in selected_pages)
        return f"将导入《{base_title}》的 {selected_count} 个分P（{page_nums}）"
