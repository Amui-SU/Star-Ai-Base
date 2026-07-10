export type VideoNoteTemplateId = "standard" | "blank";

export type VideoNoteBlockType =
  | "heading"
  | "paragraph"
  | "ai_summary"
  | "timestamp_outline"
  | "todo"
  | "questions"
  | "key_points"
  | "quote"
  | "bulleted_list"
  | "divider"
  | string;

export interface VideoNoteBlockItem {
  text?: string;
  content?: string;
  time?: number;
  timestamp?: number;
  checked?: boolean;
}

export interface VideoNoteBlock {
  id: string;
  type: VideoNoteBlockType;
  text?: string | null;
  level?: number | null;
  items?: VideoNoteBlockItem[] | null;
  checked?: boolean | null;
  source?: string | null;
}

export interface VideoNotePart {
  page: number; // 分P编号（从1开始）
  cid: number; // B站的分P CID
  part: string; // 分P标题
  duration: number; // 这个分P的时长（秒）
}

export interface VideoNoteVideo {
  bvid: string;
  title: string;
  original_title?: string | null;
  display_title?: string | null;
  folder_title?: string | null;
  owner_name?: string | null;
  duration?: number | null;
  pic_url?: string | null;
  url: string;
  parts?: VideoNotePart[] | null; // 分P信息数组
}

export interface VideoNote {
  id: number;
  user_id: number;
  workspace_id: number;
  knowledge_base_id: number;
  bvid: string;
  source_binding_id?: number | null;
  title: string;
  template_id: string;
  blocks: VideoNoteBlock[];
  tags: string[];
  summary_status: string;
  summary_generated_at?: string | null;
  export_filename_template?: string | null;
  created_at: string;
  updated_at: string;
  video?: VideoNoteVideo | null;
}

export interface VideoNoteDetailResponse {
  note: VideoNote | null;
  video: VideoNoteVideo;
  can_create: boolean;
}

export interface VideoNoteListItem {
  bvid: string;
  title: string;
  display_title?: string | null;
  folder_title?: string | null;
  note_id?: number | null;
  has_note: boolean;
  last_edited_at?: string | null;
  summary_status: string;
  tags: string[];
}

export interface VideoNoteListResponse {
  knowledge_base_id: number;
  items: VideoNoteListItem[];
}

export interface VideoNoteCreateRequest {
  knowledge_base_id: number;
  bvid: string;
  template_id: VideoNoteTemplateId;
}

export interface VideoNoteSaveRequest {
  title?: string;
  blocks: VideoNoteBlock[];
  tags: string[];
  export_filename_template?: string | null;
}

export interface VideoNoteExportResponse {
  markdown: string;
  filename: string;
}

export interface VideoNoteAiEditRequest {
  action: string;
  instruction?: string | null;
  selected_block_ids: string[];
}

export interface VideoNoteAiOperation {
  kind: string;
  block?: VideoNoteBlock | null;
  target_block_id?: string | null;
  blocks?: VideoNoteBlock[] | null;
}

export interface VideoNoteAiResponse {
  operations: VideoNoteAiOperation[];
  tag_suggestions: string[];
  message: string;
}

export interface VideoNoteListParams {
  knowledgeBaseId: number;
  q?: string;
  tag?: string;
  includeBodySearch?: boolean;
}
