const CORRUPTED_PLACEHOLDER_RE = /^[?\uFF1F\uFFFD]+$/;

export function isMissingDisplayText(value?: string | null) {
  const text = value?.trim() ?? "";
  return !text || CORRUPTED_PLACEHOLDER_RE.test(text);
}

export function displayKnowledgeBaseName(value?: string | null) {
  return isMissingDisplayText(value) ? "未命名知识库" : value!.trim();
}

export function displayFolderTitle(value?: string | null) {
  return isMissingDisplayText(value) ? "未命名收藏夹" : value!.trim();
}

export function displayVideoTitle(value?: string | null) {
  return isMissingDisplayText(value) ? "未命名视频" : value!.trim();
}
