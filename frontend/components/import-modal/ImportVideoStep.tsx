import type {
  ImportTaskProgressItem,
  VideoImportMode,
} from "@/components/import-modal/useImportModal";
import type { VideoMultiPartInfo } from "@/lib/api";

interface ImportVideoStepProps {
  knowledgeBaseId?: number | null;
  localVideoFile: File | null;
  localVideoMessage: string;
  localVideoSubmitting: boolean;
  multiPartInfo: VideoMultiPartInfo | null;
  selectedPages: number[];
  taskProgress: ImportTaskProgressItem[];
  url: string;
  urlMessage: string;
  urlSubmitting: boolean;
  videoMode: VideoImportMode;
  onCancel: () => void;
  onCancelMultiPart: () => void;
  onLocalVideoFileChange: (file: File | null) => void;
  onSubmitLocalVideo: () => void;
  onSubmitMultiPart: () => void;
  onSubmitUrl: () => void;
  onSwitchVideoMode: (mode: VideoImportMode) => void;
  onTogglePage: (page: number) => void;
  onToggleAllPages: () => void;
  onUrlChange: (value: string) => void;
}

function formatPartDuration(seconds: number) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function TaskProgressList({ tasks }: { tasks: ImportTaskProgressItem[] }) {
  if (tasks.length === 0) return null;
  return (
    <ul className="import-task-progress" aria-label="导入任务进度">
      {tasks.map((task) => (
        <li
          key={task.id}
          className={`import-task-item ${task.status ?? "pending"}`}
        >
          <span className="import-task-label">{task.label}</span>
          <span className="import-task-state">
            {task.status === "completed"
              ? "✓ 完成"
              : task.status === "failed"
                ? `✗ 失败${task.message ? `：${task.message}` : ""}`
                : `${task.step || "等待中"} ${task.progress ?? 0}%`}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function ImportVideoStep({
  knowledgeBaseId,
  localVideoFile,
  localVideoMessage,
  localVideoSubmitting,
  multiPartInfo,
  selectedPages,
  taskProgress,
  url,
  urlMessage,
  urlSubmitting,
  videoMode,
  onCancel,
  onCancelMultiPart,
  onLocalVideoFileChange,
  onSubmitLocalVideo,
  onSubmitMultiPart,
  onSubmitUrl,
  onSwitchVideoMode,
  onTogglePage,
  onToggleAllPages,
  onUrlChange,
}: ImportVideoStepProps) {
  const submitting = urlSubmitting || localVideoSubmitting;
  const disabled =
    videoMode === "url"
      ? !url.trim() || !knowledgeBaseId || urlSubmitting
      : !localVideoFile || !knowledgeBaseId || localVideoSubmitting;

  if (videoMode === "url" && multiPartInfo) {
    const allSelected = selectedPages.length === multiPartInfo.pages.length;
    return (
      <div className="import-step-body">
        <div className="import-part-header">
          <div className="import-part-title">{multiPartInfo.title}</div>
          <div className="import-part-meta">
            检测到分P视频，共 {multiPartInfo.total_parts} 个分P，已选{" "}
            {selectedPages.length} 个
          </div>
        </div>
        <label className="import-part-select-all">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={onToggleAllPages}
          />
          全选
        </label>
        <ul className="import-part-list">
          {multiPartInfo.pages.map((page) => (
            <li key={page.page}>
              <label className="import-part-item">
                <input
                  type="checkbox"
                  checked={selectedPages.includes(page.page)}
                  onChange={() => onTogglePage(page.page)}
                />
                <span className="import-part-item-title">
                  P{page.page}
                  {page.part ? `: ${page.part}` : ""}
                </span>
                <span className="import-part-item-duration">
                  {formatPartDuration(page.duration)}
                </span>
              </label>
            </li>
          ))}
        </ul>
        {urlMessage && <div className="import-message">{urlMessage}</div>}
        <div className="import-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onCancelMultiPart}
          >
            返回
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={
              selectedPages.length === 0 || !knowledgeBaseId || urlSubmitting
            }
            onClick={() => void onSubmitMultiPart()}
          >
            {urlSubmitting
              ? "导入中..."
              : `导入所选分P (${selectedPages.length})`}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="import-step-body">
      <div className="import-video-mode-tabs" aria-label="视频导入方式">
        <button
          type="button"
          className={videoMode === "url" ? "active" : ""}
          onClick={() => onSwitchVideoMode("url")}
        >
          视频 URL
        </button>
        <button
          type="button"
          className={videoMode === "local" ? "active" : ""}
          onClick={() => onSwitchVideoMode("local")}
        >
          本地视频
        </button>
      </div>

      {videoMode === "url" ? (
        <>
          <label className="import-url-label" htmlFor="import-url-input">
            粘贴视频链接
          </label>
          <textarea
            id="import-url-input"
            className="input import-url-input"
            value={url}
            onChange={(event) => onUrlChange(event.target.value)}
            placeholder="https://www.bilibili.com/video/BV..."
          />
          <p className="import-step-copy">
            当前已支持 B 站视频链接导入；抖音等平台入口已预留，后续接入解析器。
          </p>
          {urlMessage && <div className="import-message">{urlMessage}</div>}
          <TaskProgressList tasks={taskProgress} />
        </>
      ) : (
        <>
          <label
            className="import-url-label"
            htmlFor="import-local-video-input"
          >
            选择本地视频文件
          </label>
          <input
            id="import-local-video-input"
            className="import-local-video-input"
            type="file"
            accept="video/*"
            onChange={(event) =>
              onLocalVideoFileChange(event.target.files?.[0] ?? null)
            }
          />
          <div className="import-local-video-card">
            <div className="import-local-video-title">
              {localVideoFile ? localVideoFile.name : "尚未选择视频"}
            </div>
            <div className="import-local-video-meta">
              {localVideoFile
                ? `${(localVideoFile.size / 1024 / 1024).toFixed(1)} MB`
                : "支持从手机相册或电脑文件中选择视频"}
            </div>
          </div>
          <p className="import-step-copy">
            本地视频会上传到后端并通过 ASR
            转写后入库，完成后可在当前知识库中提问。
          </p>
          {localVideoMessage && (
            <div className="import-message">{localVideoMessage}</div>
          )}
          <TaskProgressList tasks={taskProgress} />
        </>
      )}
      <div className="import-actions">
        <button type="button" className="btn btn-outline" onClick={onCancel}>
          取消
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={disabled}
          onClick={() =>
            void (videoMode === "url" ? onSubmitUrl() : onSubmitLocalVideo())
          }
        >
          {submitting ? "导入中..." : "开始导入"}
        </button>
      </div>
    </div>
  );
}
