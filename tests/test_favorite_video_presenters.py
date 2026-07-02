from app.services.favorite_video_presenters import (
    dedupe_favorite_organization_items,
    favorite_organize_candidate,
    favorite_video_summary,
    legacy_valid_favorite_video_summary,
    source_binding_favorite_organization_item,
    source_binding_valid_favorite_video_summary,
)


def test_favorite_video_summary_maps_paged_media_payload():
    media = {
        "bv_id": "BV1",
        "title": "Video One",
        "cover": "cover.jpg",
        "duration": 90,
        "upper": {"name": "Uploader"},
        "cnt_info": {"play": 123},
        "intro": "Intro",
    }

    assert favorite_video_summary(media) == {
        "bvid": "BV1",
        "title": "Video One",
        "cover": "cover.jpg",
        "duration": 90,
        "owner": "Uploader",
        "play_count": 123,
        "intro": "Intro",
        "is_selected": True,
    }


def test_valid_video_summaries_preserve_legacy_and_source_binding_shapes():
    media = {
        "bvid": "BVVALID",
        "title": "Valid",
        "cover": "cover.jpg",
        "duration": 10,
        "upper": {"name": "Uploader"},
        "intro": "Intro",
        "ugc": {"first_cid": 1001},
    }

    assert legacy_valid_favorite_video_summary(media) == {
        "bvid": "BVVALID",
        "title": "Valid",
        "cover": "cover.jpg",
        "duration": 10,
        "owner": "Uploader",
        "cid": 1001,
    }
    assert source_binding_valid_favorite_video_summary(media) == {
        "bvid": "BVVALID",
        "title": "Valid",
        "cover": "cover.jpg",
        "duration": 10,
        "owner": "Uploader",
        "intro": "Intro",
        "is_selected": True,
    }


def test_valid_video_summaries_filter_missing_and_invalid_media():
    invalid_media = [
        {"title": "Missing bvid"},
        {"bvid": "BVLOST", "title": "已失效视频"},
        {"bvid": "BVDELETED", "title": "Deleted", "attr": 9},
    ]

    for media in invalid_media:
        assert legacy_valid_favorite_video_summary(media) is None
        assert source_binding_valid_favorite_video_summary(media) is None


def test_favorite_organize_candidate_normalizes_legacy_resource_payload():
    assert favorite_organize_candidate(
        {
            "bv_id": "BVVALID",
            "title": "Valid",
            "aid": "123",
            "type": "not-a-number",
        }
    ) == {
        "bvid": "BVVALID",
        "title": "Valid",
        "resource_id": 123,
        "resource_type": 2,
    }

    assert favorite_organize_candidate({"bvid": "BVNOID", "title": "No ID"}) is None
    assert (
        favorite_organize_candidate(
            {"bvid": "BVLOST", "title": "已删除视频", "id": "1"}
        )
        is None
    )


def test_source_binding_organization_item_adds_target_fields():
    assert source_binding_favorite_organization_item(
        {
            "bvid": "BVVALID",
            "title": "Valid",
            "id": "501",
            "type": "2",
        },
        default_folder_title="默认收藏夹",
    ) == {
        "bvid": "BVVALID",
        "title": "Valid",
        "resource_id": 501,
        "resource_type": 2,
        "target_folder_id": None,
        "target_folder_title": "默认收藏夹",
        "reason": "待手动分类",
    }


def test_dedupe_favorite_organization_items_preserves_first_resource_pair():
    first = {"resource_id": 1, "resource_type": 2, "title": "First"}
    duplicate = {"resource_id": 1, "resource_type": 2, "title": "Duplicate"}
    other = {"resource_id": 1, "resource_type": 4, "title": "Other"}

    assert dedupe_favorite_organization_items([first, duplicate, other]) == [
        first,
        other,
    ]
