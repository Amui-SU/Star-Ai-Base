"use client";

import { useEffect, useState } from "react";
import {
  getSavedLocalConnection,
  isNativeShell,
  normalizeLocalApiBaseUrl,
  saveLocalConnection,
} from "@/lib/localConnection";
import { scanLocalConnectionQrCode } from "@/lib/localConnectionScanner";
import { requestWithNativeFallback } from "@/lib/nativeHttp";

export default function LocalConnectionSettings() {
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [address, setAddress] = useState("");
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"info" | "error">("info");
  const [testing, setTesting] = useState(false);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    const native = isNativeShell();
    setEnabled(native);
    if (!native) return;
    const saved = getSavedLocalConnection();
    setAddress(saved?.apiBaseUrl || "");
    setOpen(!saved);
  }, []);

  if (!enabled) return null;

  const testAndSave = async (nextAddress = address) => {
    setTesting(true);
    setMessage("");
    setMessageKind("info");
    try {
      const apiBaseUrl = normalizeLocalApiBaseUrl(nextAddress);
      const response = await requestWithNativeFallback(`${apiBaseUrl}/health`, {
        method: "GET",
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`后端返回 ${response.status}`);
      }
      saveLocalConnection(apiBaseUrl);
      setAddress(apiBaseUrl);
      setMessageKind("info");
      setMessage("连接可用，已保存");
    } catch (error) {
      setMessageKind("error");
      setMessage(error instanceof Error ? error.message : "连接失败");
    } finally {
      setTesting(false);
    }
  };

  const scanAndSave = async () => {
    setScanning(true);
    setMessage("");
    setMessageKind("info");
    try {
      const apiBaseUrl = await scanLocalConnectionQrCode();
      setAddress(apiBaseUrl);
      await testAndSave(apiBaseUrl);
    } catch (error) {
      setMessageKind("error");
      setMessage(error instanceof Error ? error.message : "扫码失败");
    } finally {
      setScanning(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="local-connection-trigger"
        onClick={() => setOpen(true)}
      >
        连接设置
      </button>
      {open && (
        <div className="modal-backdrop" onMouseDown={() => setOpen(false)}>
          <div
            className="modal-card local-connection-modal"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="local-connection-head">
              <div>
                <div className="modal-title text-left">连接电脑端</div>
                <div className="modal-subtitle text-left">
                  换局域网后只需要改这里的电脑地址。
                </div>
              </div>
              <button
                type="button"
                className="provider-config-close"
                onClick={() => setOpen(false)}
                aria-label="关闭连接设置"
              >
                ×
              </button>
            </div>

            <label className="local-connection-field">
              <span>电脑端地址</span>
              <input
                className="input local-connection-input"
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                placeholder="192.168.1.200 或 http://192.168.1.200:8000"
                autoFocus
              />
            </label>

            {message && (
              <div
                className={`local-connection-message ${
                  messageKind === "error"
                    ? "local-connection-message-error"
                    : ""
                }`}
                role="status"
              >
                {message}
              </div>
            )}

            <div className="local-connection-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => void scanAndSave()}
                disabled={scanning || testing}
              >
                {scanning ? "扫码中..." : "扫码"}
              </button>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setOpen(false)}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void testAndSave()}
                disabled={testing || !address.trim()}
              >
                {testing ? "测试中..." : "测试并保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
