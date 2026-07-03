from app.services.folder_ingestion_plan import build_video_map, diff_folder_videos


def test_build_video_map_filters_invalid_excluded_and_unselected_videos():
    videos = [
        {"bvid": "BVKEEP", "title": "Keep", "attr": 0, "upper": {"name": "UP"}},
        {"bvid": "BVEXCLUDE", "title": "Excluded", "attr": 0},
        {"bvid": "BVUNSELECTED", "title": "Unselected", "attr": 0},
        {"bvid": "BVINVALID", "title": "已失效视频", "attr": 9},
        {"title": "Missing bvid", "attr": 0},
    ]

    video_map, skipped_invalid = build_video_map(
        videos,
        include_bvids={"BVKEEP", "BVEXCLUDE", "BVINVALID"},
        exclude_bvids={"BVEXCLUDE"},
    )

    assert skipped_invalid == 1
    assert list(video_map) == ["BVKEEP"]
    assert video_map["BVKEEP"] == {
        "title": "Keep",
        "cid": None,
        "intro": None,
        "cover": None,
        "duration": None,
        "owner_name": "UP",
        "owner_mid": None,
    }


def test_diff_folder_videos_keeps_removed_empty_for_partial_sync():
    added, removed = diff_folder_videos(
        current_bvids={"BVNEW"},
        existing_bvids={"BVOLD"},
        partial=True,
    )

    assert added == {"BVNEW"}
    assert removed == set()


def test_diff_folder_videos_removes_missing_videos_for_full_sync():
    added, removed = diff_folder_videos(
        current_bvids={"BVNEW", "BVKEEP"},
        existing_bvids={"BVOLD", "BVKEEP"},
        partial=False,
    )

    assert added == {"BVNEW"}
    assert removed == {"BVOLD"}
