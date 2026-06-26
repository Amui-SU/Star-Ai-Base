"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";

import {
  importApi,
  sourceBindingApi,
  type ImportMethod,
  type QRCodeResponse,
} from "@/lib/api";

interface Props {
  open: boolean;
  knowledgeBaseId?: number | null;
  hasBilibiliBinding: boolean;
  onClose: () => void;
  onBound: () => void;
  onImported?: () => void;
}

type Step = "methods" | "bilibili" | "video";
type VideoImportMode = "url" | "local";
const MAX_QR_POLL_ATTEMPTS = 150;

export default function ImportModal({
  open,
  knowledgeBaseId,
  hasBilibiliBinding,
  onClose,
  onBound,
  onImported,
}: Props) {
  const [step, setStep] = useState<Step>("methods");
  const [methods, setMethods] = useState<ImportMethod[]>([]);
  const [qr, setQr] = useState<QRCodeResponse | null>(null);
  const [qrStatus, setQrStatus] = useState<
    "idle" | "loading" | "ready" | "scanned" | "success" | "error"
  >("idle");
  const [qrErrorMessage, setQrErrorMessage] =
    useState("二维码获取失败，请检查网络或重试");
  const [polling, setPolling] = useState(false);
  const qrPollAttemptsRef = useRef(0);
  const [videoMode, setVideoMode] = useState<VideoImportMode>("url");
  const [url, setUrl] = useState("");
  const [urlMessage, setUrlMessage] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);
  const [localVideoFile, setLocalVideoFile] = useState<File | null>(null);
  const [localVideoMessage, setLocalVideoMessage] = useState("");
  const [localVideoSubmitting, setLocalVideoSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      const timer = window.setTimeout(() => {
        setStep("methods");
        setPolling(false);
        setQr(null);
        setQrStatus("idle");
        setQrErrorMessage("二维码获取失败，请检查网络或重试");
        qrPollAttemptsRef.current = 0;
        setVideoMode("url");
        setUrl("");
        setUrlMessage("");
        setUrlSubmitting(false);
        setLocalVideoFile(null);
        setLocalVideoMessage("");
        setLocalVideoSubmitting(false);
      }, 0);
      return () => window.clearTimeout(timer);
    }
    importApi
      .methods()
      .then((res) => setMethods(res.methods))
      .catch(() => setMethods([]));
  }, [open]);

  const getQR = async () => {
    setQrStatus("loading");
    setQrErrorMessage("二维码获取失败，请检查网络或重试");
    try {
      const data = await sourceBindingApi.getBilibiliQRCode();
      setQr(data);
      setQrStatus("ready");
      qrPollAttemptsRef.current = 0;
      setPolling(true);
    } catch (err) {
      setQrErrorMessage(
        err instanceof Error ? err.message : "二维码获取失败，请检查网络或重试",
      );
      setQrStatus("error");
    }
  };

  useEffect(() => {
    if (step !== "bilibili" || hasBilibiliBinding) return;
    const timer = window.setTimeout(() => void getQR(), 0);
    return () => window.clearTimeout(timer);
  }, [step, hasBilibiliBinding]);

  useEffect(() => {
    if (!polling || !qr) return;
    const timer = window.setInterval(async () => {
      qrPollAttemptsRef.current += 1;
      try {
        const res = await sourceBindingApi.pollBilibiliQRCode(qr.qrcode_key);
        if (res.status === "scanned") setQrStatus("scanned");
        if (res.status === "confirmed") {
          setPolling(false);
          setQrStatus("success");
          window.setTimeout(() => {
            onBound();
            onClose();
          }, 500);
        }
        if (res.status === "expired") {
          setPolling(false);
          setQrErrorMessage("二维码已过期");
          setQrStatus("error");
        }
        if (
          qrPollAttemptsRef.current >= MAX_QR_POLL_ATTEMPTS &&
          res.status !== "confirmed" &&
          res.status !== "expired"
        ) {
          setPolling(false);
          setQrErrorMessage("二维码等待超时，请重新获取");
          setQrStatus("error");
        }
      } catch {
        setPolling(false);
        setQrErrorMessage("二维码状态检查失败，请重新获取");
        setQrStatus("error");
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [polling, qr, onBound, onClose]);

  const submitUrl = async () => {
    if (!url.trim() || urlSubmitting) return;
    setUrlSubmitting(true);
    setUrlMessage("");
    try {
      const res = await importApi.importUrl({
        url: url.trim(),
        source_type: "auto",
        knowledge_base_id: knowledgeBaseId,
      });
      setUrlMessage(res.message);
      if (res.ok) {
        onImported?.();
        setUrl("");
      }
    } catch (err) {
      setUrlMessage(err instanceof Error ? err.message : "导入失败");
    } finally {
      setUrlSubmitting(false);
    }
  };

  const submitLocalVideo = async () => {
    if (!localVideoFile || localVideoSubmitting) return;
    setLocalVideoSubmitting(true);
    setLocalVideoMessage("");
    try {
      const res = await importApi.importLocalVideo({
        file: localVideoFile,
        knowledge_base_id: knowledgeBaseId,
        title: localVideoFile.name,
      });
      setLocalVideoMessage(res.message);
      if (res.ok) {
        onImported?.();
        setLocalVideoFile(null);
      }
    } catch (err) {
      setLocalVideoMessage(err instanceof Error ? err.message : "导入失败");
    } finally {
      setLocalVideoSubmitting(false);
    }
  };

  if (!open) return null;

  const methodList =
    methods.length > 0
      ? methods
      : [
          {
            id: "bilibili_favorites",
            label: "B 站收藏夹",
            description: "扫码绑定账号后导入收藏夹资料",
            status: "available",
            level: 2,
          },
          {
            id: "video_import",
            label: "导入视频",
            description: "支持视频 URL 或本地视频文件，直接导入到当前知识库",
            status: "available",
            level: 1,
          },
        ];

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className={`modal-card import-modal ${
          step === "methods" ? "import-modal-methods" : "import-modal-step"
        }`}
        onMouseDown={(event) => event.stopPropagation()}
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
              onClick={() => {
                setStep("methods");
                setPolling(false);
                qrPollAttemptsRef.current = 0;
              }}
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
                onClick={() => {
                  if (method.id === "bilibili_favorites") setStep("bilibili");
                  if (
                    method.id === "video_url" ||
                    method.id === "video_import"
                  ) {
                    setStep("video");
                  }
                }}
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
                onClick={() => {
                  setVideoMode("url");
                  setLocalVideoMessage("");
                }}
              >
                视频 URL
              </button>
              <button
                type="button"
                className={videoMode === "local" ? "active" : ""}
                onClick={() => {
                  setVideoMode("local");
                  setUrlMessage("");
                }}
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
                {urlMessage && (
                  <div className="import-message">{urlMessage}</div>
                )}
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
              <button
                type="button"
                className="btn btn-outline"
                onClick={onClose}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={
                  videoMode === "url"
                    ? !url.trim() || !knowledgeBaseId || urlSubmitting
                    : !localVideoFile ||
                      !knowledgeBaseId ||
                      localVideoSubmitting
                }
                onClick={() =>
                  void (videoMode === "url" ? submitUrl() : submitLocalVideo())
                }
              >
                {urlSubmitting || localVideoSubmitting
                  ? "导入中..."
                  : "开始导入"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
