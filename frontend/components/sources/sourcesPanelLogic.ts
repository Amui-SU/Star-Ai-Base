export type SourcesFolderCountSource = "bili" | "filtered" | "db";

export interface SourcesFolderForStatus {
  media_id: number;
  media_count: number;
  count_source?: SourcesFolderCountSource;
}

export interface SourcesFolderStatus {
  media_id: number;
  indexed_count: number;
  media_count?: number;
  last_sync_at?: string | null;
}

export interface SourcesFolderDisplayStatus {
  label: "未入库" | "已入库" | "有更新";
  className: "empty" | "ok" | "partial";
  indexedCount: number;
  totalCount?: number;
}

export function formatFolderSyncTime(value?: string) {
  if (!value) return null;
  try {
    let dateStr = value;
    if (!value.includes("T") && !value.includes("Z")) {
      dateStr = value.replace(" ", "T") + "Z";
    }
    const date = new Date(dateStr);
    if (Number.isNaN(date.getTime())) return null;

    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hour = String(date.getHours()).padStart(2, "0");
    const minute = String(date.getMinutes()).padStart(2, "0");
    return `${month}/${day} ${hour}:${minute}`;
  } catch {
    return null;
  }
}

export function getSourcesFolderStatus({
  folders,
  statusMap,
  mediaId,
  totalInBilibili,
}: {
  folders: SourcesFolderForStatus[];
  statusMap: Record<number, SourcesFolderStatus>;
  mediaId: number;
  totalInBilibili: number;
}): SourcesFolderDisplayStatus {
  const status = statusMap[mediaId];
  const indexedCount = status?.indexed_count ?? 0;
  const lastSync = status?.last_sync_at;
  const folder = folders.find((item) => item.media_id === mediaId);
  const countSource = folder?.count_source ?? "bili";
  let totalCount = totalInBilibili;
  if (countSource === "filtered") {
    totalCount = folder?.media_count ?? totalInBilibili;
  } else if (status?.media_count != null) {
    totalCount = status.media_count;
  }

  if (!lastSync) {
    return { label: "未入库", className: "empty", indexedCount };
  }

  if (indexedCount >= totalCount) {
    return { label: "已入库", className: "ok", indexedCount, totalCount };
  }

  if (indexedCount < totalCount && indexedCount > 0) {
    return {
      label: "有更新",
      className: "partial",
      indexedCount,
      totalCount,
    };
  }

  return { label: "已入库", className: "ok", indexedCount, totalCount };
}

export function getSourcesBuildButtonText({
  building,
  progressStep,
  selectedCount,
  selectedVideoCount,
  selectedFolderIds,
  targetKnowledgeBase,
  folders,
  statusMap,
}: {
  building: boolean;
  progressStep?: string;
  selectedCount: number;
  selectedVideoCount: number;
  selectedFolderIds: number[];
  targetKnowledgeBase: string;
  folders: SourcesFolderForStatus[];
  statusMap: Record<number, SourcesFolderStatus>;
}) {
  if (building) return progressStep || "处理中...";
  if (selectedCount === 0 && selectedVideoCount === 0) {
    return "选择收藏夹或视频";
  }

  if (selectedCount === 0) {
    return `入库 ${selectedVideoCount} 个视频到${targetKnowledgeBase}`;
  }

  if (selectedVideoCount > 0) {
    return `入库 ${selectedCount} 个收藏夹和 ${selectedVideoCount} 个视频到${targetKnowledgeBase}`;
  }

  const hasUnindexed = selectedFolderIds.some((id) => {
    const folder = folders.find((item) => item.media_id === id);
    if (!folder) return false;
    return !statusMap[id]?.last_sync_at;
  });

  if (hasUnindexed) {
    return `入库 ${selectedCount} 个收藏夹到${targetKnowledgeBase}`;
  }
  return `更新 ${selectedCount} 个收藏夹到${targetKnowledgeBase}`;
}
