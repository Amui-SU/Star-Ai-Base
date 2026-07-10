# AI时间戳功能数据需求

## 一、数据库字段补充

### 1. VideoCache 表新增字段

```python
# 分P元信息
page_number = Column(Integer, nullable=True)  # 分P编号（1, 2, 3...）
part_title = Column(String(500), nullable=True)  # 分P原始标题
total_parts = Column(Integer, nullable=True)  # 总分P数

# 时间轴数据
subtitle_timeline_json = Column(JSON, nullable=True)  # 完整字幕时间轴
# 格式示例：
# [
#   {"from": 0.0, "to": 3.5, "content": "大家好"},
#   {"from": 3.5, "to": 7.2, "content": "今天我们来讲..."}
# ]
```

**说明：**

- `page_number`, `part_title`, `total_parts` - 方便AI识别和展示分P信息
- `subtitle_timeline_json` - 保存完整的字幕时间轴，支持精确定位
- `outline_json` - 已有字段，包含AI摘要的分段时间戳

### 2. 为什么需要这些字段？

#### 分P元信息的用途：

1. **前端展示** - 在笔记中显示"来自《教程合集》第1集（共3集）：基础入门"
2. **AI理解** - 让AI知道这是系列视频的第几部分，上下文更完整
3. **时间戳定位** - 用户点击时间戳时，需要知道跳转到哪个分P

#### 时间轴数据的用途：

1. **精确定位** - AI生成的笔记带时间戳时，可以精确跳转到视频位置
2. **片段提取** - 支持"这段在3:45到5:20讲了什么"的精确查询
3. **内容索引** - 按时间段组织笔记内容

## 二、API 接口补充

### 1. 分P视频导入时保存完整信息

**修改点：** `app/services/import_persistence.py`

```python
async def store_imported_video_content(
    *,
    content: VideoContent,
    workspace_id: int,
    knowledge_base_id: int,
    cid: int | None = None,
    # 新增参数
    page_number: int | None = None,
    part_title: str | None = None,
    total_parts: int | None = None,
    subtitle_timeline: list[dict] | None = None,
    # ... 其他参数
) -> None:
    # ... 保存时填充新字段
    cache.page_number = page_number
    cache.part_title = part_title
    cache.total_parts = total_parts
    cache.subtitle_timeline_json = subtitle_timeline
```

### 2. 修改字幕下载保留时间轴

**修改点：** `app/services/bilibili_media.py`

```python
def subtitle_with_timeline_from_payload(data: dict) -> tuple[str, list[dict]]:
    """
    提取字幕文本和时间轴

    Returns:
        (text, timeline)
        - text: 纯文本内容（用于向量检索）
        - timeline: 完整时间轴数据（用于时间戳定位）
    """
    texts = []
    timeline = []

    for item in data.get("body", []):
        content = item.get("content", "")
        if content:
            texts.append(content)
            timeline.append({
                "from": item.get("from", 0),
                "to": item.get("to", 0),
                "content": content,
            })

    return "\n".join(texts), timeline
```

### 3. 分P导入时传递元信息

**修改点：** `app/routers/imports.py` 的 `import_multi_part`

```python
# 为每个分P创建导入任务时，传递完整的分P信息
background_tasks.add_task(
    _run_bilibili_video_import,
    task.task_id,
    bvid,
    current_workspace.id,
    kb.id,
    page_info["cid"],
    # 新增分P元信息
    page_number=page_info["page"],
    part_title=page_info["part"],
    total_parts=part_info["total_parts"],
)
```

## 三、前端接口补充

### 1. 查询视频详情时返回时间轴数据

**新增接口：** `GET /videos/{bvid}/timeline`

```python
class VideoTimelineResponse(BaseModel):
    bvid: str
    cid: int | None
    page_number: int | None
    part_title: str | None
    total_parts: int | None
    subtitle_timeline: list[dict] | None
    outline: list[dict] | None  # AI摘要的分段时间戳
```

### 2. 笔记中的时间戳跳转

前端需要：

1. 知道当前笔记对应的 bvid 和 cid
2. 获取完整的分P信息（如果是多P视频）
3. 生成正确的B站播放链接，包含时间参数

示例：`https://www.bilibili.com/video/{bvid}?p={page_number}&t={timestamp}`

## 四、实施优先级

### 高优先级（必需）

- ✅ `page_number`, `part_title`, `total_parts` 字段
- ✅ 分P导入时保存元信息
- ✅ 前端接口返回分P信息

### 中优先级（建议）

- 🔶 `subtitle_timeline_json` 字段
- 🔶 保存完整字幕时间轴
- 🔶 视频时间轴查询接口

### 低优先级（可选）

- 🔵 按时间段检索
- 🔵 片段提取功能

## 五、数据库迁移

```python
# 新增字段的迁移脚本
ALTER TABLE video_cache
ADD COLUMN page_number INTEGER,
ADD COLUMN part_title VARCHAR(500),
ADD COLUMN total_parts INTEGER,
ADD COLUMN subtitle_timeline_json JSON;
```

## 六、向后兼容

- 所有新字段都设置为 `nullable=True`
- 旧数据的这些字段为 NULL，不影响现有功能
- 单P视频的 `page_number=1`, `total_parts=1`
- 没有字幕的视频 `subtitle_timeline_json=None`
