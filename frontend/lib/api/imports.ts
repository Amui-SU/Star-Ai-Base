import { request } from "./client";
import type { ImportMethod, ImportUrlResponse } from "./importTypes";

export const importApi = {
  methods: () => request<{ methods: ImportMethod[] }>("/imports/methods"),

  importUrl: (data: {
    url: string;
    source_type?: string;
    knowledge_base_id?: number | null;
  }) =>
    request<ImportUrlResponse>("/imports/url", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  importLocalVideo: (data: {
    file: File;
    knowledge_base_id?: number | null;
    title?: string;
  }) => {
    const formData = new FormData();
    formData.set("file", data.file);
    if (data.knowledge_base_id) {
      formData.set("knowledge_base_id", String(data.knowledge_base_id));
    }
    if (data.title?.trim()) {
      formData.set("title", data.title.trim());
    }
    return request<ImportUrlResponse>("/imports/local-video", {
      method: "POST",
      body: formData,
    });
  },
};
