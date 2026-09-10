"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  importApi,
  sourceBindingApi,
  type ImportMethod,
  type QRCodeResponse,
  type VideoMultiPartInfo,
} from "@/lib/api";
import { useImportTaskTracking } from "./useImportTaskTracking";

const BVID_RE = /BV[0-9A-Za-z]{10}/;

export interface ImportTaskProgressItem {
  id: string;
  label: string;
  status?: string;
  progress?: number;
  step?: string | null;
  message?: string;
}

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
  const [multiPartInfo, setMultiPartInfo] = useState<VideoMultiPartInfo | null>(
    null,
  );
  const [selectedPages, setSelectedPages] = useState<number[]>([]);
  const { trackTasks, taskProgress } = useImportTaskTracking(onImported);
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
        setMultiPartInfo(null);
        setSelectedPages([]);
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
      const trimmedUrl = url.trim();

      // B 站链接先检测分P；检测失败不阻塞，回退到单条导入
      if (BVID_RE.test(trimmedUrl)) {
        try {
          const detected = await importApi.detectMultiPart(trimmedUrl);
          const info = detected.ok ? detected.multi_part_info : null;
          if (info?.is_multi_part) {
            setMultiPartInfo(info);
            setSelectedPages(info.pages.map((page) => page.page));
            return;
          }
        } catch {
          /* 检测不可用时按单条导入处理 */
        }
      }

      const res = await importApi.importUrl({
        url: trimmedUrl,
        source_type: "auto",
        knowledge_base_id: knowledgeBaseId,
      });
      setUrlMessage(res.message);
      if (res.ok) {
        setUrl("");
        if (res.task_id) {
          const taskId = res.task_id;
          trackTasks([{ id: taskId, label: res.bvid || "视频导入" }]);
        }
      }
    } catch (err) {
      setUrlMessage(err instanceof Error ? err.message : "导入失败");
    } finally {
      setUrlSubmitting(false);
    }
  };

  const togglePage = (page: number) => {
    setSelectedPages((current) =>
      current.includes(page)
        ? current.filter((value) => value !== page)
        : [...current, page].sort((a, b) => a - b),
    );
  };

  const toggleAllPages = () => {
    setSelectedPages((current) =>
      multiPartInfo && current.length < multiPartInfo.pages.length
        ? multiPartInfo.pages.map((page) => page.page)
        : [],
    );
  };

  const cancelMultiPart = () => {
    setMultiPartInfo(null);
    setSelectedPages([]);
    setUrlMessage("");
  };

  const submitMultiPart = async () => {
    if (
      !multiPartInfo ||
      selectedPages.length === 0 ||
      !knowledgeBaseId ||
      urlSubmitting
    ) {
      return;
    }
    setUrlSubmitting(true);
    setUrlMessage("");
    try {
      const res = await importApi.importMultiPart({
        url: url.trim(),
        knowledge_base_id: knowledgeBaseId,
        page_indices: selectedPages,
      });
      setUrlMessage(res.message);
      if (res.ok) {
        setUrl("");
        // task_ids 与选中的分P顺序一致
        trackTasks(
          res.task_ids.map((taskId, index) => ({
            id: taskId,
            label: `P${selectedPages[index] ?? index + 1}`,
          })),
        );
        setMultiPartInfo(null);
        setSelectedPages([]);
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
        if (res.task_id) {
          const taskId = res.task_id;
          const label = localVideoFile.name;
          trackTasks([{ id: taskId, label }]);
        }
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
    cancelMultiPart,
    getQR,
    localVideoFile,
    localVideoMessage,
    localVideoSubmitting,
    methodList,
    multiPartInfo,
    openMethod,
    qr,
    qrErrorMessage,
    qrStatus,
    returnToMethods,
    selectedPages,
    setLocalVideoFile,
    setUrl,
    step,
    submitLocalVideo,
    submitMultiPart,
    submitUrl,
    switchVideoMode,
    taskProgress,
    toggleAllPages,
    togglePage,
    url,
    urlMessage,
    urlSubmitting,
    videoMode,
  };
}
