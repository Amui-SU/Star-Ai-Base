"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type FavoriteFolder,
  type FolderStatus,
  knowledgeBaseApi,
  sourceBindingApi,
  type Video,
} from "@/lib/api";

export interface SourcesPanelFolder extends FavoriteFolder {
  videos?: Video[];
  expanded?: boolean;
  loading?: boolean;
  count_source?: "bili" | "filtered" | "db";
}

export function useSourcesPanelData({
  sourceBindingId,
  knowledgeBaseId,
}: {
  sourceBindingId: number;
  knowledgeBaseId: number;
}) {
  const [folders, setFolders] = useState<SourcesPanelFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusMap, setStatusMap] = useState<Record<number, FolderStatus>>({});
  const [message, setMessage] = useState<string | null>(null);

  const loadFolders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sourceBindingApi.getFavorites(sourceBindingId);
      setFolders(data.map((folder) => ({ ...folder, count_source: "bili" })));
      setMessage(null);
    } catch (err) {
      setFolders([]);
      setMessage(
        err instanceof Error ? err.message : "加载收藏夹失败，请稍后重试",
      );
    }
    setLoading(false);
  }, [sourceBindingId]);

  const loadStatuses = useCallback(async () => {
    if (!knowledgeBaseId) return;
    try {
      const stats = await knowledgeBaseApi.stats(knowledgeBaseId);
      const nextStatusMap: Record<number, FolderStatus> = {};
      if (stats.folders) {
        stats.folders.forEach(
          (folder: {
            media_id: number;
            indexed_count: number;
            media_count: number;
            last_sync_at: string | null;
          }) => {
            nextStatusMap[folder.media_id] = {
              media_id: folder.media_id,
              indexed_count: folder.indexed_count,
              media_count: folder.media_count,
              last_sync_at: folder.last_sync_at,
            };
          },
        );
      }
      setStatusMap(nextStatusMap);
    } catch {
      // 状态接口失败不影响主列表展示。
    }
  }, [knowledgeBaseId]);

  const refreshSourcesData = useCallback(async () => {
    setMessage(null);
    await loadFolders();
    await loadStatuses();
  }, [loadFolders, loadStatuses]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadFolders().then(loadStatuses);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadFolders, loadStatuses]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setMessage(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [sourceBindingId, knowledgeBaseId]);

  return {
    folders,
    loading,
    loadStatuses,
    message,
    refreshSourcesData,
    setFolders,
    setMessage,
    statusMap,
  };
}
