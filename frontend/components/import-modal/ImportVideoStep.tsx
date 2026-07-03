import type { VideoImportMode } from "@/components/import-modal/useImportModal";

interface ImportVideoStepProps {
  knowledgeBaseId?: number | null;
  localVideoFile: File | null;
  localVideoMessage: string;
  localVideoSubmitting: boolean;
  url: string;
  urlMessage: string;
  urlSubmitting: boolean;
  videoMode: VideoImportMode;
  onCancel: () => void;
  onLocalVideoFileChange: (file: File | null) => void;
  onSubmitLocalVideo: () => void;
  onSubmitUrl: () => void;
  onSwitchVideoMode: (mode: VideoImportMode) => void;
  onUrlChange: (value: string) => void;
}

export default function ImportVideoStep({
  knowledgeBaseId,
  localVideoFile,
  localVideoMessage,
  localVideoSubmitting,
  url,
  urlMessage,
  urlSubmitting,
  videoMode,
  onCancel,
  onLocalVideoFileChange,
  onSubmitLocalVideo,
  onSubmitUrl,
  onSwitchVideoMode,
  onUrlChange,
}: ImportVideoStepProps) {
  const submitting = urlSubmitting || localVideoSubmitting;
  const disabled =
    videoMode === "url"
      ? !url.trim() || !knowledgeBaseId || urlSubmitting
      : !localVideoFile || !knowledgeBaseId || localVideoSubmitting;

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
