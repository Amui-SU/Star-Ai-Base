"""测试B站分P视频处理功能"""

import pytest
from app.services.bilibili_multi_part import (
    detect_multi_part_video,
    format_part_title,
    extract_page_info,
    validate_page_selection,
    build_import_summary,
)


def test_detect_single_part_video():
    """测试检测单P视频"""
    video_info = {
        "bvid": "BV1xx411c7XZ",
        "cid": 12345,
        "title": "单P视频",
        "videos": 1,
        "pages": [{"cid": 12345, "page": 1, "part": "单P视频", "duration": 600}],
    }

    result = detect_multi_part_video(video_info)

    assert result["is_multi_part"] is False
    assert result["total_parts"] == 1
    assert len(result["pages"]) == 1
    assert result["default_cid"] == 12345


def test_detect_multi_part_video():
    """测试检测分P视频"""
    video_info = {
        "bvid": "BV1xx411c7XZ",
        "cid": 12345,
        "title": "教程合集",
        "videos": 3,
        "pages": [
            {"cid": 12345, "page": 1, "part": "基础入门", "duration": 1200},
            {"cid": 12346, "page": 2, "part": "进阶技巧", "duration": 1500},
            {"cid": 12347, "page": 3, "part": "实战案例", "duration": 1800},
        ],
    }

    result = detect_multi_part_video(video_info)

    assert result["is_multi_part"] is True
    assert result["total_parts"] == 3
    assert len(result["pages"]) == 3
    assert result["default_cid"] == 12345


def test_format_part_title_single():
    """测试单P视频标题格式化"""
    title = format_part_title("教程", 1, "基础", 1)
    assert title == "教程"


def test_format_part_title_multi_with_part_name():
    """测试分P视频标题格式化（带分P名称）"""
    title = format_part_title("教程合集", 1, "基础入门", 3)
    assert title == "教程合集 P1/3: 基础入门"

    title = format_part_title("教程合集", 2, "进阶技巧", 3)
    assert title == "教程合集 P2/3: 进阶技巧"


def test_format_part_title_multi_without_part_name():
    """测试分P视频标题格式化（无分P名称）"""
    title = format_part_title("教程合集", 1, None, 3)
    assert title == "教程合集 P1/3"

    title = format_part_title("教程合集", 2, "", 3)
    assert title == "教程合集 P2/3"


def test_format_part_title_same_as_base():
    """测试分P名称与基础标题相同时的格式化"""
    title = format_part_title("教程合集", 1, "教程合集", 3)
    assert title == "教程合集 P1/3"


def test_extract_page_info():
    """测试提取分P信息"""
    page_data = {"cid": 12345, "page": 1, "part": "基础入门", "duration": 1200}

    info = extract_page_info(page_data)

    assert info["cid"] == 12345
    assert info["page"] == 1
    assert info["part"] == "基础入门"
    assert info["duration"] == 1200


def test_validate_page_selection_empty_allowed():
    """测试验证空选择（允许）"""
    is_valid, msg = validate_page_selection([], 3, allow_empty=True)
    assert is_valid is True
    assert msg == ""


def test_validate_page_selection_empty_not_allowed():
    """测试验证空选择（不允许）"""
    is_valid, msg = validate_page_selection([], 3, allow_empty=False)
    assert is_valid is False
    assert "未选择" in msg


def test_validate_page_selection_valid():
    """测试验证有效选择"""
    is_valid, msg = validate_page_selection([1, 2, 3], 3, allow_empty=False)
    assert is_valid is True
    assert msg == ""

    is_valid, msg = validate_page_selection([1, 3], 5, allow_empty=False)
    assert is_valid is True


def test_validate_page_selection_out_of_range():
    """测试验证超出范围的选择"""
    is_valid, msg = validate_page_selection([1, 2, 5], 3, allow_empty=False)
    assert is_valid is False
    assert "超出范围" in msg


def test_validate_page_selection_duplicate():
    """测试验证重复选择"""
    is_valid, msg = validate_page_selection([1, 2, 2], 3, allow_empty=False)
    assert is_valid is False
    assert "重复" in msg


def test_validate_page_selection_invalid_type():
    """测试验证无效类型"""
    is_valid, msg = validate_page_selection([1, "2", 3], 3, allow_empty=False)
    assert is_valid is False
    assert "整数" in msg


def test_build_import_summary_all():
    """测试构建导入摘要（全部分P）"""
    pages = [
        {"page": 1, "part": "基础"},
        {"page": 2, "part": "进阶"},
        {"page": 3, "part": "实战"},
    ]
    summary = build_import_summary("教程合集", pages, 3)
    assert "全部 3 个分P" in summary
    assert "教程合集" in summary


def test_build_import_summary_single():
    """测试构建导入摘要（单个分P）"""
    pages = [{"page": 2, "part": "进阶技巧"}]
    summary = build_import_summary("教程合集", pages, 3)
    assert "P2" in summary
    assert "进阶技巧" in summary


def test_build_import_summary_partial():
    """测试构建导入摘要（部分分P）"""
    pages = [
        {"page": 1, "part": "基础"},
        {"page": 3, "part": "实战"},
    ]
    summary = build_import_summary("教程合集", pages, 3)
    assert "2 个分P" in summary
    assert "P1, P3" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
