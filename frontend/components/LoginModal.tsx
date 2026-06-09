"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { sourceBindingApi, QRCodeResponse } from "@/lib/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onBound: () => void;
}

export default function LoginModal({ isOpen, onClose, onBound }: Props) {
  const [qr, setQr] = useState<QRCodeResponse | null>(null);
  const [status, setStatus] = useState<
    "loading" | "ready" | "scanned" | "success" | "error"
  >("loading");
  const [polling, setPolling] = useState(false);

  const getQR = async () => {
    setStatus("loading");
    try {
      const data = await sourceBindingApi.getBilibiliQRCode();
      console.log("二维码获取成功:", data.qrcode_key);
      setQr(data);
      setStatus("ready");
      setPolling(true);
    } catch (e) {
      console.error("二维码获取失败:", e);
      setStatus("error");
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (isOpen) getQR();
      else {
        setPolling(false);
        setQr(null);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isOpen]);

  useEffect(() => {
    if (!polling || !qr) return;
    const timer = setInterval(async () => {
      try {
        const res = await sourceBindingApi.pollBilibiliQRCode(qr.qrcode_key);
        console.log("轮询状态:", res.status);
        if (res.status === "scanned") setStatus("scanned");
        else if (res.status === "confirmed") {
          console.log("绑定确认成功");
          setPolling(false);
          setStatus("success");
          setTimeout(() => onBound(), 500);
        } else if (res.status === "expired") {
          console.log("二维码过期");
          setPolling(false);
          setStatus("error");
        }
      } catch (e) {
        console.warn("轮询失败，重新获取二维码:", e);
        setPolling(false);
        getQR();
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [polling, qr, onBound]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">绑定 B 站账号</h2>
        <p className="modal-subtitle">
          使用哔哩哔哩 APP 扫描，用于导入收藏夹内容
        </p>

        <div className="mt-4 flex justify-center">
          {status === "loading" && (
            <div className="w-48 h-48 flex items-center justify-center border border-dashed border-[var(--border)] rounded-2xl">
              <div className="w-8 h-8 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {(status === "ready" || status === "scanned") && qr && (
            <div className="relative">
              <Image
                src={qr.qrcode_image_base64}
                alt="B站绑定二维码"
                width={192}
                height={192}
                unoptimized
                className="w-48 h-48 rounded-2xl border border-[var(--border)]"
              />
              {status === "scanned" && (
                <div className="absolute inset-0 bg-white/90 rounded-2xl flex flex-col items-center justify-center">
                  <div className="status-pill">已扫码</div>
                  <span className="text-sm mt-3">请在手机上确认</span>
                </div>
              )}
            </div>
          )}

          {status === "success" && (
            <div className="w-48 h-48 flex flex-col items-center justify-center">
              <div className="status-pill">绑定成功</div>
              <p className="text-sm text-[var(--muted)] mt-3">B 站账号已关联</p>
            </div>
          )}

          {status === "error" && (
            <div className="w-48 h-48 flex flex-col items-center justify-center">
              <p className="text-sm text-[var(--muted)] mb-3">二维码已过期</p>
              <button onClick={getQR} className="btn btn-primary">
                重新获取
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
