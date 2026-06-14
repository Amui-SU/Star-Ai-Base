export interface ChatScopeSelection {
  folderIds: number[];
  bvids: string[];
}

export const EMPTY_CHAT_SCOPE: ChatScopeSelection = {
  folderIds: [],
  bvids: [],
};

export function normalizeScope(scope: ChatScopeSelection): ChatScopeSelection {
  return {
    folderIds: [...new Set(scope.folderIds)].sort(
      (left, right) => left - right,
    ),
    bvids: [...new Set(scope.bvids)].sort(),
  };
}

export function scopeEquals(
  left: ChatScopeSelection,
  right: ChatScopeSelection,
): boolean {
  const normalizedLeft = normalizeScope(left);
  const normalizedRight = normalizeScope(right);

  return (
    normalizedLeft.folderIds.length === normalizedRight.folderIds.length &&
    normalizedLeft.folderIds.every(
      (folderId, index) => folderId === normalizedRight.folderIds[index],
    ) &&
    normalizedLeft.bvids.length === normalizedRight.bvids.length &&
    normalizedLeft.bvids.every(
      (bvid, index) => bvid === normalizedRight.bvids[index],
    )
  );
}

export function scopeSummary(scope: ChatScopeSelection): string {
  const normalized = normalizeScope(scope);
  const parts: string[] = [];

  if (normalized.folderIds.length > 0) {
    parts.push(`${normalized.folderIds.length} 个收藏夹`);
  }
  if (normalized.bvids.length > 0) {
    parts.push(`${normalized.bvids.length} 个视频`);
  }

  return parts.length > 0 ? parts.join("、") : "整个知识库";
}

export function toScopePayload(scope: ChatScopeSelection): {
  folder_ids?: number[];
  bvids?: string[];
} {
  const normalized = normalizeScope(scope);

  return {
    ...(normalized.folderIds.length > 0
      ? { folder_ids: normalized.folderIds }
      : {}),
    ...(normalized.bvids.length > 0 ? { bvids: normalized.bvids } : {}),
  };
}
