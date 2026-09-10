// 分P导入的视频以 `${bvid}_p${page}` 作为存储ID（与后端
// app/services/bilibili_multi_part.py 保持一致），构造 B 站链接前需还原
const PART_VIDEO_ID_RE = /^([0-9A-Za-z]+)_p(\d+)$/;

export function splitPartBvid(videoId: string): {
  bvid: string;
  page: number | null;
} {
  const match = PART_VIDEO_ID_RE.exec(videoId ?? "");
  if (!match) return { bvid: videoId, page: null };
  return { bvid: match[1], page: Number(match[2]) };
}

export function bilibiliVideoUrl(videoId: string): string {
  const { bvid, page } = splitPartBvid(videoId);
  const base = `https://www.bilibili.com/video/${bvid}`;
  return page && page > 1 ? `${base}?p=${page}` : base;
}
