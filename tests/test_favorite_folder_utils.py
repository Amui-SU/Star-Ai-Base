def test_default_favorite_folder_detection_matches_source_binding_rules():
    from app.services.favorite_folders import is_default_favorite_folder

    assert is_default_favorite_folder({"is_default": True})
    assert is_default_favorite_folder({"type": 1})
    assert is_default_favorite_folder({"fav_state": 1})
    assert is_default_favorite_folder({"title": "默认收藏夹"})
    assert is_default_favorite_folder({"is_default": False, "type": 1})
    assert not is_default_favorite_folder({"default": True})
    assert not is_default_favorite_folder({"isDefault": True})
    assert not is_default_favorite_folder({"attr": 1})
    assert not is_default_favorite_folder({"title": "学习资料"})


def test_default_favorite_folder_detection_preserves_legacy_session_rules():
    from app.services.favorite_folders import is_default_favorite_folder

    options = {
        "explicit_flag_overrides": True,
        "include_alias_flags": True,
        "include_attr": True,
    }

    assert not is_default_favorite_folder({"is_default": False, "type": 1}, **options)
    assert is_default_favorite_folder({"default": True}, **options)
    assert is_default_favorite_folder({"isDefault": True}, **options)
    assert is_default_favorite_folder({"attr": 1}, **options)
    assert is_default_favorite_folder({"title": "默认收藏夹"}, **options)
