"use client";

import { useCallback, useState } from "react";

export interface SourcesSelectionFolder {
  media_id: number;
  videos?: { bvid: string }[];
}

export interface SourcesSelectionState {
  selected: Set<number>;
  selectedVideos: Set<string>;
}

function createEmptySelection(): SourcesSelectionState {
  return {
    selected: new Set(),
    selectedVideos: new Set(),
  };
}

export function toggleFolderSelection({
  folders,
  folderId,
  selected,
  selectedVideos,
}: {
  folders: SourcesSelectionFolder[];
  folderId: number;
  selected: Set<number>;
  selectedVideos: Set<string>;
}): SourcesSelectionState {
  const nextSelected = new Set(selected);
  const nextSelectedVideos = new Set(selectedVideos);

  if (nextSelected.has(folderId)) {
    nextSelected.delete(folderId);
    return {
      selected: nextSelected,
      selectedVideos: nextSelectedVideos,
    };
  }

  nextSelected.add(folderId);
  const folder = folders.find((item) => item.media_id === folderId);
  folder?.videos?.forEach((video) => nextSelectedVideos.delete(video.bvid));

  return {
    selected: nextSelected,
    selectedVideos: nextSelectedVideos,
  };
}

export function toggleVideoSelection({
  folderId,
  bvid,
  selected,
  selectedVideos,
}: {
  folderId: number;
  bvid: string;
  selected: Set<number>;
  selectedVideos: Set<string>;
}): SourcesSelectionState {
  const nextSelected = new Set(selected);
  const nextSelectedVideos = new Set(selectedVideos);

  if (nextSelected.has(folderId)) {
    nextSelected.delete(folderId);
  }

  if (nextSelectedVideos.has(bvid)) {
    nextSelectedVideos.delete(bvid);
  } else {
    nextSelectedVideos.add(bvid);
  }

  return {
    selected: nextSelected,
    selectedVideos: nextSelectedVideos,
  };
}

export function useSourcesSelection(folders: SourcesSelectionFolder[]) {
  const [selection, setSelection] =
    useState<SourcesSelectionState>(createEmptySelection);

  const resetSelection = useCallback(() => {
    setSelection(createEmptySelection());
  }, []);

  const selectFolder = useCallback(
    (folderId: number) => {
      setSelection((current) =>
        toggleFolderSelection({
          folders,
          folderId,
          selected: current.selected,
          selectedVideos: current.selectedVideos,
        }),
      );
    },
    [folders],
  );

  const selectVideo = useCallback((folderId: number, bvid: string) => {
    setSelection((current) =>
      toggleVideoSelection({
        folderId,
        bvid,
        selected: current.selected,
        selectedVideos: current.selectedVideos,
      }),
    );
  }, []);

  return {
    selected: selection.selected,
    selectedVideos: selection.selectedVideos,
    resetSelection,
    toggleFolderSelection: selectFolder,
    toggleVideoSelection: selectVideo,
  };
}
