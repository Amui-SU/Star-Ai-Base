"""分P视频相关的Pydantic模型"""

from pydantic import BaseModel, Field


class VideoPageInfo(BaseModel):
    """单个分P的信息"""

    cid: int | None = None
    page: int = Field(..., ge=1, description="分P编号，从1开始")
    part: str = Field(default="", description="分P标题")
    duration: int = Field(default=0, ge=0, description="时长（秒）")


class VideoMultiPartInfo(BaseModel):
    """分P视频信息"""

    bvid: str
    title: str
    is_multi_part: bool = Field(description="是否为分P视频")
    total_parts: int = Field(ge=1, description="总分P数")
    pages: list[VideoPageInfo] = Field(default_factory=list, description="分P列表")
    default_cid: int | None = Field(default=None, description="默认cid（第一P）")
    description: str | None = Field(default=None, description="视频简介")
    owner_name: str | None = Field(default=None, description="UP主名称")
    pic_url: str | None = Field(default=None, description="封面图片")


class ImportMultiPartRequest(BaseModel):
    """导入分P视频请求"""

    url: str = Field(..., min_length=3, description="B站视频URL")
    knowledge_base_id: int = Field(..., description="知识库ID")
    page_indices: list[int] = Field(
        default_factory=list, description="要导入的分P索引列表（从1开始），空=全部导入"
    )
    title_format: str = Field(
        default="auto",
        description="标题格式：auto=自动（含分P信息），original=原始标题，custom=自定义",
    )
    custom_title_prefix: str | None = Field(
        default=None, description="自定义标题前缀（当title_format=custom时使用）"
    )


class ImportMultiPartResponse(BaseModel):
    """导入分P视频响应"""

    ok: bool
    message: str
    bvid: str | None = None
    total_selected: int = Field(default=0, description="选择导入的分P数量")
    task_ids: list[str] = Field(default_factory=list, description="任务ID列表")
    import_summary: str | None = Field(default=None, description="导入摘要")


class DetectMultiPartResponse(BaseModel):
    """检测分P视频响应"""

    ok: bool
    message: str
    multi_part_info: VideoMultiPartInfo | None = None
