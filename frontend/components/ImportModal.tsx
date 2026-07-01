"use client";

import Image from "next/image";

import { useImportModal } from "@/components/import-modal/useImportModal";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  knowledgeBaseId?: number | null;
  hasBilibiliBinding: boolean;
  onClose: () => void;
  onBound: () => void;
  onImported?: () => void;
}

export default function ImportModal({
  open,
  knowledgeBaseId,
  hasBilibiliBinding,
  onClose,
  onBound,
  onImported,
}: Props) {
  const {
    getQR,
    localVideoFile,
    localVideoMessage,
    localVideoSubmitting,
    methodList,
    openMethod,
    qr,
    qrErrorMessage,
    qrStatus,
    returnToMethods,
    setLocalVideoFile,
    setUrl,
    step,
    submitLocalVideo,
    submitUrl,
    switchVideoMode,
    url,
    urlMessage,
    urlSubmitting,
    videoMode,
  } = useImportModal({
    hasBilibiliBinding,
    knowledgeBaseId,
    onBound,
    onClose,
    onImported,
    open,
  });

  if (!open) return null;

  return (
    <ModalShell
      cardClassName={`import-modal ${
        step === "methods" ? "import-modal-methods" : "import-modal-step"
      }`}
      onClose={onClose}
    >
      <div className="import-modal-head">
        <div>
          <div className="modal-title text-left">
            {step === "methods"
              ? "导入资料"
              : step === "bilibili"
                ? "B 站收藏夹"
                : "导入视频"}
          </div>
          <div className="modal-subtitle text-left">
            选择导入方式，资料会进入当前知识库
          </div>
        </div>
        {step !== "methods" && (
          <button
            type="button"
            className="import-back-btn"
            onClick={returnToMethods}
          >
            返回
          </button>
        )}
      </div>

      {step === "methods" && (
        <div className="import-method-grid">
          {methodList.map((method) => (
            <button
              key={method.id}
              type="button"
              className={`import-method-card ${method.status !== "available" ? "disabled" : ""}`}
              onClick={() => openMethod(method)}
              disabled={
                method.status !== "available" &&
                method.id !== "bilibili_favorites"
              }
            >
              <span className="import-method-kicker">
                {method.level === 2 ? "二级绑定" : "直接导入"}
              </span>
              <span className="import-method-title">{method.label}</span>
              <span className="import-method-copy">{method.description}</span>
              {method.status !== "available" && (
                <span className="import-method-status">待接入</span>
              )}
            </button>
          ))}
        </div>
      )}

      {step === "bilibili" && (
        <div className="import-step-body">
          {hasBilibiliBinding ? (
            <div className="import-bound-card">
              <div className="status-pill ok">已绑定</div>
              <p>B 站收藏夹已可在左侧列表中选择并入库。</p>
            </div>
          ) : (
            <>
              <p className="import-step-copy">
                使用哔哩哔哩 APP 扫码绑定账号，绑定完成后会显示收藏夹资料。
              </p>
              <div className="import-qr-wrap">
                {qrStatus === "loading" && (
                  <div className="import-qr-placeholder">
                    <div className="w-8 h-8 border-2 border-(--accent) border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
                {(qrStatus === "ready" || qrStatus === "scanned") && qr && (
                  <div className="relative">
                    <Image
                      src={qr.qrcode_image_base64}
                      alt="B站绑定二维码"
                      width={192}
                      height={192}
                      unoptimized
                      className="import-qr-image"
                    />
                    {qrStatus === "scanned" && (
                      <div className="import-qr-overlay">
                        <div className="status-pill">已扫码</div>
                        <span>请在手机上确认</span>
                      </div>
                    )}
                  </div>
                )}
                {qrStatus === "success" && (
                  <div className="import-qr-placeholder">
                    <div className="status-pill ok">绑定成功</div>
                  </div>
                )}
                {qrStatus === "error" && (
                  <div className="import-qr-placeholder">
                    <p>{qrErrorMessage}</p>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => void getQR()}
                    >
                      重新获取
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {step === "video" && (
        <div className="import-step-body">
          <div className="import-video-mode-tabs" aria-label="视频导入方式">
            <button
              type="button"
              className={videoMode === "url" ? "active" : ""}
              onClick={() => switchVideoMode("url")}
            >
              视频 URL
            </button>
            <button
              type="button"
              className={videoMode === "local" ? "active" : ""}
              onClick={() => switchVideoMode("local")}
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
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://www.bilibili.com/video/BV..."
              />
              <p className="import-step-copy">
                当前已支持 B
                站视频链接导入；抖音等平台入口已预留，后续接入解析器。
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
                  setLocalVideoFile(event.target.files?.[0] ?? null)
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
            <button type="button" className="btn btn-outline" onClick={onClose}>
              取消
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={
                videoMode === "url"
                  ? !url.trim() || !knowledgeBaseId || urlSubmitting
                  : !localVideoFile || !knowledgeBaseId || localVideoSubmitting
              }
              onClick={() =>
                void (videoMode === "url" ? submitUrl() : submitLocalVideo())
              }
            >
              {urlSubmitting || localVideoSubmitting ? "导入中..." : "开始导入"}
            </button>
          </div>
        </div>
      )}
    </ModalShell>
  );
}
