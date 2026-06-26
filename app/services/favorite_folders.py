from typing import Any, Mapping


DEFAULT_FAVORITE_FOLDER_TITLE = "默认收藏夹"


def is_default_favorite_folder(
    folder: Mapping[str, Any],
    *,
    explicit_flag_overrides: bool = False,
    include_alias_flags: bool = False,
    include_attr: bool = False,
) -> bool:
    if "is_default" in folder:
        if explicit_flag_overrides:
            return bool(folder.get("is_default"))
        if folder.get("is_default"):
            return True
    if include_alias_flags:
        for key in ("default", "isDefault"):
            if key in folder:
                if explicit_flag_overrides:
                    return bool(folder.get(key))
                if folder.get(key):
                    return True
    if folder.get("type") == 1:
        return True
    if folder.get("fav_state") == 1:
        return True
    if include_attr and folder.get("attr") == 1:
        return True
    title = (folder.get("title") or "").strip()
    return title == DEFAULT_FAVORITE_FOLDER_TITLE


def is_legacy_default_favorite_folder(folder: Mapping[str, Any]) -> bool:
    return is_default_favorite_folder(
        folder,
        explicit_flag_overrides=True,
        include_alias_flags=True,
        include_attr=True,
    )
