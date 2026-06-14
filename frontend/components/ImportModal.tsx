"use client";

import { useEffect, useState } from "react";
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

type Step = "methods" | "bilibili" | "url";

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
  const [polling, setPolling] = useState(false);
  const [url, setUrl] = useState("");
  const [urlMessage, setUrlMessage] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      const timer = window.setTimeout(() => {
        setStep("methods");
        setPolling(false);
        setQr(null);
        setQrStatus("idle");
        setUrl("");
        setUrlMessage("");
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
    try {
      const data = await sourceBindingApi.getBilibiliQRCode();
      setQr(data);
      setQrStatus("ready");
      setPolling(true);
    } catch {
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
          setQrStatus("error");
        }
      } catch {
        setPolling(false);
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
            id: "video_url",
            label: "视频 URL",
            description: "粘贴 B 站视频链接，直接导入到当前知识库",
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
                  : "视频 URL"}
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
                  if (method.id === "video_url") setStep("url");
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
                      <p>二维码已过期</p>
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

        {step === "url" && (
          <div className="import-step-body">
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
                disabled={!url.trim() || !knowledgeBaseId || urlSubmitting}
                onClick={() => void submitUrl()}
              >
                {urlSubmitting ? "导入中..." : "开始导入"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
