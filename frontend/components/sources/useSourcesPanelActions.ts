"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useState,
} from "react";

import {
  type OrganizePreviewResponse,
  sourceBindingApi,
  type Video,
} from "@/lib/api";
import { displayVideoTitle } from "@/lib/displayNames";

import type { SourcesPanelFolder } from "@/components/sources/useSourcesPanelData";

export function useSourcesPanelActions({
  folders,
  knowledgeBaseId,
  onMessage,
  setFolders,
  sourceBindingId,
}: {
  folders: SourcesPanelFolder[];
  knowledgeBaseId: number;
  onMessage: (message: string | null) => void;
  setFolders: Dispatch<SetStateAction<SourcesPanelFolder[]>>;
  sourceBindingId: number;
}) {
  const [customVideoNames, setCustomVideoNames] = useState<
    Record<string, string>
  >({});
  const [editingVideoId, setEditingVideoId] = useState<string | null>(null);
  const [editingVideoName, setEditingVideoName] = useState("");
  const [savingVideoId, setSavingVideoId] = useState<string | null>(null);
  const [organizeOpen, setOrganizeOpen] = useState(false);
  const [organizeLoading, setOrganizeLoading] = useState(false);
  const [organizePreview, setOrganizePreview] =
    useState<OrganizePreviewResponse | null>(null);
  const [organizeMessage, setOrganizeMessage] = useState<string | null>(null);

  const getOriginalVideoTitle = useCallback(
    (video: Video) => displayVideoTitle(video.original_title || video.title),
    [],
  );

  const getVideoTitle = useCallback(
    (video: Video) =>
      displayVideoTitle(
        customVideoNames[video.bvid] ||
          video.display_title ||
          video.custom_title ||
          video.title,
      ),
    [customVideoNames],
  );

  const startRenameVideo = useCallback(
    (video: Video) => {
      setEditingVideoId(video.bvid);
      setEditingVideoName(getVideoTitle(video));
    },
    [getVideoTitle],
  );

  const applyVideoTitle = useCallback(
    (videos: Video[] | undefined, bvid: string, customTitle: string | null) =>
      videos?.map((video) =>
        video.bvid === bvid
          ? {
              ...video,
              custom_title: customTitle,
              display_title: customTitle || getOriginalVideoTitle(video),
              title: customTitle || getOriginalVideoTitle(video),
            }
          : video,
      ),
    [getOriginalVideoTitle],
  );

  const saveVideoTitle = useCallback(
    async (video: Video, title: string) => {
      const originalTitle = getOriginalVideoTitle(video);
      const trimmed = title.trim();
      const customTitle =
        !trimmed || trimmed === originalTitle ? null : trimmed;
      setSavingVideoId(video.bvid);
      try {
        const res = await sourceBindingApi.updateVideoTitle(sourceBindingId, {
          bvid: video.bvid,
          title: customTitle,
          knowledge_base_id: knowledgeBaseId,
        });
        const nextCustomTitle = res.custom_title ?? null;
        setCustomVideoNames((prev) => {
          const next = { ...prev };
          if (nextCustomTitle) {
            next[video.bvid] = nextCustomTitle;
          } else {
            delete next[video.bvid];
          }
          return next;
        });
        setFolders((prev) =>
          prev.map((folder) => ({
            ...folder,
            videos: applyVideoTitle(folder.videos, video.bvid, nextCustomTitle),
          })),
        );
        setEditingVideoId(null);
        setEditingVideoName("");
        onMessage(nextCustomTitle ? "已保存自定义视频名" : "已恢复原始视频名");
      } catch (err) {
        onMessage(err instanceof Error ? err.message : "保存视频名称失败");
      } finally {
        setSavingVideoId(null);
      }
    },
    [
      applyVideoTitle,
      getOriginalVideoTitle,
      knowledgeBaseId,
      onMessage,
      setFolders,
      sourceBindingId,
    ],
  );

  const openOrganizePreview = useCallback(
    async (folderId: number) => {
      setOrganizeMessage(null);
      setOrganizePreview(null);
      setOrganizeOpen(true);
      setOrganizeLoading(true);
      try {
        const res = await sourceBindingApi.organizePreview(
          sourceBindingId,
          folderId,
        );
        setOrganizePreview(res);
      } catch {
        setOrganizeMessage("预览失败，请稍后重试");
      } finally {
        setOrganizeLoading(false);
      }
    },
    [sourceBindingId],
  );

  const toggleExpand = useCallback(
    async (id: number) => {
      setFolders((prev) =>
        prev.map((folder) => {
          if (folder.media_id !== id) return folder;
          if (folder.expanded) return { ...folder, expanded: false };
          if (folder.videos) return { ...folder, expanded: true };
          return { ...folder, expanded: true, loading: true };
        }),
      );

      const folder = folders.find((item) => item.media_id === id);
      if (!folder?.videos) {
        try {
          const res = await sourceBindingApi.getAllFavoriteVideos(
            sourceBindingId,
            id,
            knowledgeBaseId,
          );
          setFolders((prev) =>
            prev.map((item) =>
              item.media_id === id
                ? {
                    ...item,
                    videos: res.videos,
                    loading: false,
                    media_count: res.total,
                    count_source: "filtered",
                  }
                : item,
            ),
          );
        } catch {
          setFolders((prev) =>
            prev.map((item) =>
              item.media_id === id ? { ...item, loading: false } : item,
            ),
          );
        }
      }
    },
    [folders, knowledgeBaseId, setFolders, sourceBindingId],
  );

  return {
    editingVideoId,
    editingVideoName,
    getOriginalVideoTitle,
    getVideoTitle,
    organizeLoading,
    organizeMessage,
    organizeOpen,
    organizePreview,
    openOrganizePreview,
    saveVideoTitle,
    savingVideoId,
    setEditingVideoId,
    setEditingVideoName,
    setOrganizeMessage,
    setOrganizeOpen,
    startRenameVideo,
    toggleExpand,
  };
}
