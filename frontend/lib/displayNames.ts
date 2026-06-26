const CORRUPTED_PLACEHOLDER_RE = /^[?\uFF1F\uFFFD]+$/;

function cleanDisplayText(value?: string | null) {
  const text = value?.trim() ?? "";
  return !text || CORRUPTED_PLACEHOLDER_RE.test(text) ? null : text;
}

export function isMissingDisplayText(value?: string | null) {
  return cleanDisplayText(value) === null;
}

export function displayKnowledgeBaseName(value?: string | null) {
  return cleanDisplayText(value) ?? "未命名知识库";
}

export function displayFolderTitle(value?: string | null) {
  return cleanDisplayText(value) ?? "未命名收藏夹";
}

export function displayVideoTitle(value?: string | null) {
  return cleanDisplayText(value) ?? "未命名视频";
}
