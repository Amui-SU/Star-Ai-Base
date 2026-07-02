import { describe, expect, it } from "vitest";

import {
  toggleFolderSelection,
  toggleVideoSelection,
} from "@/components/sources/useSourcesSelection";

describe("sources selection state", () => {
  it("selects a whole folder and clears individually selected videos in that folder", () => {
    const result = toggleFolderSelection({
      folders: [
        {
          media_id: 10,
          videos: [{ bvid: "BV1A" }, { bvid: "BV1B" }],
        },
      ],
      folderId: 10,
      selected: new Set<number>(),
      selectedVideos: new Set(["BV1A", "BVKEEP"]),
    });

    expect(Array.from(result.selected)).toEqual([10]);
    expect(Array.from(result.selectedVideos)).toEqual(["BVKEEP"]);
  });

  it("selects a single video and clears the whole-folder selection", () => {
    const result = toggleVideoSelection({
      folderId: 10,
      bvid: "BV1A",
      selected: new Set([10, 20]),
      selectedVideos: new Set<string>(),
    });

    expect(Array.from(result.selected)).toEqual([20]);
    expect(Array.from(result.selectedVideos)).toEqual(["BV1A"]);
  });

  it("toggles an already selected single video off", () => {
    const result = toggleVideoSelection({
      folderId: 10,
      bvid: "BV1A",
      selected: new Set<number>(),
      selectedVideos: new Set(["BV1A", "BVKEEP"]),
    });

    expect(Array.from(result.selected)).toEqual([]);
    expect(Array.from(result.selectedVideos)).toEqual(["BVKEEP"]);
  });
});
