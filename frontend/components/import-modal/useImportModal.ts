"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  importApi,
  sourceBindingApi,
  type ImportMethod,
  type QRCodeResponse,
} from "@/lib/api";

export type ImportModalStep = "methods" | "bilibili" | "video";
export type VideoImportMode = "url" | "local";

const MAX_QR_POLL_ATTEMPTS = 150;

const defaultMethods: ImportMethod[] = [
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

interface UseImportModalParams {
  hasBilibiliBinding: boolean;
  knowledgeBaseId?: number | null;
  onBound: () => void;
  onClose: () => void;
  onImported?: () => void;
  open: boolean;
}

export function useImportModal({
  hasBilibiliBinding,
  knowledgeBaseId,
  onBound,
  onClose,
  onImported,
  open,
}: UseImportModalParams) {
  const [step, setStep] = useState<ImportModalStep>("methods");
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

  const methodList = useMemo(
    () => (methods.length > 0 ? methods : defaultMethods),
    [methods],
  );

  const returnToMethods = () => {
    setStep("methods");
    setPolling(false);
    qrPollAttemptsRef.current = 0;
  };

  const openMethod = (method: ImportMethod) => {
    if (method.id === "bilibili_favorites") setStep("bilibili");
    if (method.id === "video_url" || method.id === "video_import") {
      setStep("video");
    }
  };

  const switchVideoMode = (nextMode: VideoImportMode) => {
    setVideoMode(nextMode);
    if (nextMode === "url") {
      setLocalVideoMessage("");
    } else {
      setUrlMessage("");
    }
  };

  return {
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
  };
}
