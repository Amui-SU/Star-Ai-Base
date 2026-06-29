"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type BuildStatus,
  type KnowledgeBaseBuildRequest,
  knowledgeBaseApi,
} from "@/lib/api";

import type { SourcesPanelFolder } from "@/components/sources/useSourcesPanelData";

export function useSourcesKnowledgeBuild({
  excludeBvids,
  folders,
  knowledgeBaseId,
  onBuildDone,
  onBuildingChange,
  onLoadStatuses,
  onMessage,
  selected,
  selectedVideos,
  sourceBindingId,
}: {
  excludeBvids: string[];
  folders: SourcesPanelFolder[];
  knowledgeBaseId: number;
  onBuildDone?: () => void;
  onBuildingChange?: (building: boolean) => void;
  onLoadStatuses: () => Promise<void>;
  onMessage: (message: string | null) => void;
  selected: Set<number>;
  selectedVideos: Set<string>;
  sourceBindingId: number;
}) {
  const [building, setBuilding] = useState(false);
  const [progress, setProgress] = useState<BuildStatus | null>(null);

  useEffect(() => {
    onBuildingChange?.(building);
    return () => onBuildingChange?.(false);
  }, [building, onBuildingChange]);

  const resetBuildProgress = useCallback(() => {
    setProgress(null);
  }, []);

  const startBuild = useCallback(async () => {
    if (selected.size === 0 && selectedVideos.size === 0) return;
    setBuilding(true);
    onMessage(null);
    setProgress(null);

    try {
      const selectedVideoBvids = Array.from(selectedVideos);
      const videoFolderIds = new Set<number>();
      folders.forEach((folder) => {
        folder.videos?.forEach((video) => {
          if (
            selectedVideos.has(video.bvid) &&
            !selected.has(folder.media_id)
          ) {
            videoFolderIds.add(folder.media_id);
          }
        });
      });
      const res = await knowledgeBaseApi.build(knowledgeBaseId, {
        source_binding_id: sourceBindingId,
        folder_ids: Array.from(selected),
        ...(selectedVideoBvids.length > 0
          ? {
              video_folder_ids: Array.from(videoFolderIds),
              bvids: selectedVideoBvids,
            }
          : {}),
        ...(excludeBvids.length > 0 ? { exclude_bvids: excludeBvids } : {}),
      } as KnowledgeBaseBuildRequest);

      const poll = async () => {
        const status = await knowledgeBaseApi.getBuildStatus(
          knowledgeBaseId,
          res.task_id,
        );
        setProgress(status);

        if (status.status === "running" || status.status === "pending") {
          setTimeout(poll, 1000);
        } else {
          setBuilding(false);
          if (status.status === "completed") {
            onMessage(status.message || "构建完成");
            await onLoadStatuses();
            onBuildDone?.();
          } else if (status.status === "failed") {
            onMessage(`构建失败: ${status.message}`);
          } else if (status.status === "interrupted") {
            onMessage(`构建已中断: ${status.message || "请重新发起"}`);
          } else {
            onMessage(status.message || `构建已停止: ${status.status}`);
          }
        }
      };
      poll();
    } catch {
      setBuilding(false);
      onMessage("构建失败，请重试");
    }
  }, [
    excludeBvids,
    folders,
    knowledgeBaseId,
    onBuildDone,
    onLoadStatuses,
    onMessage,
    selected,
    selectedVideos,
    sourceBindingId,
  ]);

  return {
    building,
    progress,
    resetBuildProgress,
    startBuild,
  };
}
