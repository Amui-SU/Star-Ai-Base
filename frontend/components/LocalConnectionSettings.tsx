"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  getSavedLocalConnection,
  isNativeShell,
  normalizeLocalApiBaseUrl,
  saveLocalConnection,
} from "@/lib/localConnection";
import { scanLocalConnectionQrCode } from "@/lib/localConnectionScanner";
import { requestWithNativeFallback } from "@/lib/nativeHttp";

const CONNECTION_SAVED_MESSAGE =
  "\u8fde\u63a5\u53ef\u7528\uff0c\u5df2\u4fdd\u5b58";

const getInitialLocalConnectionState = () => {
  const native = isNativeShell();
  const saved = native ? getSavedLocalConnection() : null;
  return {
    enabled: native,
    address: saved?.apiBaseUrl || "",
    open: native && !saved,
  };
};

export default function LocalConnectionSettings() {
  const [initialState] = useState(getInitialLocalConnectionState);
  const [enabled] = useState(initialState.enabled);
  const [open, setOpen] = useState(initialState.open);
  const [address, setAddress] = useState(initialState.address);
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"info" | "error">("info");
  const [savedNotice, setSavedNotice] = useState("");
  const [testing, setTesting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const savedNoticeTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (savedNoticeTimerRef.current) {
        window.clearTimeout(savedNoticeTimerRef.current);
      }
    };
  }, []);

  if (!enabled) return null;

  const showSavedNotice = () => {
    if (savedNoticeTimerRef.current) {
      window.clearTimeout(savedNoticeTimerRef.current);
    }
    setSavedNotice(CONNECTION_SAVED_MESSAGE);
    savedNoticeTimerRef.current = window.setTimeout(() => {
      setSavedNotice("");
      savedNoticeTimerRef.current = null;
    }, 2600);
  };

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
      setOpen(false);
      showSavedNotice();
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

  const portalTarget = typeof document === "undefined" ? null : document.body;

  const savedNoticeNode = savedNotice ? (
    <div className="local-connection-saved-notice" role="status">
      {savedNotice}
    </div>
  ) : null;

  const settingsModalNode = open ? (
    <div
      className="modal-backdrop local-connection-modal-backdrop"
      onMouseDown={() => setOpen(false)}
    >
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
          />
        </label>

        {message && (
          <div
            className={`local-connection-message ${
              messageKind === "error" ? "local-connection-message-error" : ""
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
  ) : null;

  return (
    <>
      <button
        type="button"
        className="local-connection-trigger"
        onClick={() => {
          setSavedNotice("");
          setOpen(true);
        }}
      >
        <span className="local-connection-trigger-label">连接设置</span>
      </button>
      {portalTarget && savedNoticeNode
        ? createPortal(savedNoticeNode, portalTarget)
        : savedNoticeNode}
      {portalTarget && settingsModalNode
        ? createPortal(settingsModalNode, portalTarget)
        : settingsModalNode}
    </>
  );
}
