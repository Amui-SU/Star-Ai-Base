import { describe, expect, it } from "vitest";
import {
  formatFolderSyncTime,
  getSourcesBuildButtonText,
  getSourcesFolderStatus,
} from "@/components/sources/sourcesPanelLogic";

describe("sourcesPanelLogic", () => {
  it("formats backend sync timestamps for compact folder metadata", () => {
    const expected = new Date("2026-06-27T08:09:00Z");
    const month = String(expected.getMonth() + 1).padStart(2, "0");
    const day = String(expected.getDate()).padStart(2, "0");
    const hour = String(expected.getHours()).padStart(2, "0");
    const minute = String(expected.getMinutes()).padStart(2, "0");

    expect(formatFolderSyncTime("2026-06-27 08:09:00")).toBe(
      `${month}/${day} ${hour}:${minute}`,
    );
    expect(formatFolderSyncTime("not-a-date")).toBeNull();
    expect(formatFolderSyncTime()).toBeNull();
  });

  it("returns empty, ok, and partial folder status labels", () => {
    expect(
      getSourcesFolderStatus({
        folders: [{ media_id: 1, media_count: 3, count_source: "bili" }],
        statusMap: {},
        mediaId: 1,
        totalInBilibili: 3,
      }),
    ).toEqual({
      label: "未入库",
      className: "empty",
      indexedCount: 0,
    });

    expect(
      getSourcesFolderStatus({
        folders: [{ media_id: 1, media_count: 3, count_source: "bili" }],
        statusMap: {
          1: {
            media_id: 1,
            indexed_count: 3,
            media_count: 3,
            last_sync_at: "2026-06-27T08:09:00Z",
          },
        },
        mediaId: 1,
        totalInBilibili: 3,
      }),
    ).toEqual({
      label: "已入库",
      className: "ok",
      indexedCount: 3,
      totalCount: 3,
    });

    expect(
      getSourcesFolderStatus({
        folders: [{ media_id: 1, media_count: 5, count_source: "filtered" }],
        statusMap: {
          1: {
            media_id: 1,
            indexed_count: 2,
            media_count: 5,
            last_sync_at: "2026-06-27T08:09:00Z",
          },
        },
        mediaId: 1,
        totalInBilibili: 10,
      }),
    ).toEqual({
      label: "有更新",
      className: "partial",
      indexedCount: 2,
      totalCount: 5,
    });
  });

  it("builds the source ingest button label from selection state", () => {
    const folders = [
      { media_id: 10, media_count: 3, count_source: "bili" as const },
      { media_id: 20, media_count: 2, count_source: "bili" as const },
    ];

    expect(
      getSourcesBuildButtonText({
        building: false,
        selectedCount: 0,
        selectedVideoCount: 0,
        selectedFolderIds: [],
        targetKnowledgeBase: "「测试库」",
        folders,
        statusMap: {},
      }),
    ).toBe("选择收藏夹或视频");

    expect(
      getSourcesBuildButtonText({
        building: false,
        selectedCount: 0,
        selectedVideoCount: 2,
        selectedFolderIds: [],
        targetKnowledgeBase: "「测试库」",
        folders,
        statusMap: {},
      }),
    ).toBe("入库 2 个视频到「测试库」");

    expect(
      getSourcesBuildButtonText({
        building: false,
        selectedCount: 1,
        selectedVideoCount: 2,
        selectedFolderIds: [10],
        targetKnowledgeBase: "「测试库」",
        folders,
        statusMap: {},
      }),
    ).toBe("入库 1 个收藏夹和 2 个视频到「测试库」");

    expect(
      getSourcesBuildButtonText({
        building: false,
        selectedCount: 1,
        selectedVideoCount: 0,
        selectedFolderIds: [20],
        targetKnowledgeBase: "「测试库」",
        folders,
        statusMap: {
          20: {
            media_id: 20,
            indexed_count: 2,
            media_count: 2,
            last_sync_at: "2026-06-27T08:09:00Z",
          },
        },
      }),
    ).toBe("更新 1 个收藏夹到「测试库」");

    expect(
      getSourcesBuildButtonText({
        building: true,
        progressStep: "正在处理字幕",
        selectedCount: 1,
        selectedVideoCount: 0,
        selectedFolderIds: [10],
        targetKnowledgeBase: "「测试库」",
        folders,
        statusMap: {},
      }),
    ).toBe("正在处理字幕");
  });
});
