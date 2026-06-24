"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import {
  localConnectionApi,
  type LocalLanAddressResponse,
  systemAuthApi,
  type SystemUser,
} from "@/lib/api";

interface Props {
  user: SystemUser;
  onUserChange: (user: SystemUser) => void;
  onLogout: () => void;
  onOpenAdmin?: () => void;
}

export default function UserMenu({
  user,
  onUserChange,
  onLogout,
  onOpenAdmin,
}: Props) {
  const initial = user.display_name?.charAt(0)?.toUpperCase() || "?";
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedLan, setCopiedLan] = useState(false);
  const [showLanQr, setShowLanQr] = useState(false);
  const [lanAddress, setLanAddress] = useState<LocalLanAddressResponse | null>(
    null,
  );
  const [lanLoading, setLanLoading] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [displayName, setDisplayName] = useState(user.display_name);
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  useEffect(() => {
    if (!open || lanAddress) return;
    let cancelled = false;
    void Promise.resolve()
      .then(() => {
        if (cancelled) return null;
        setLanLoading(true);
        return localConnectionApi.lanAddress();
      })
      .then((response) => {
        if (!cancelled && response) setLanAddress(response);
      })
      .catch(() => {
        if (!cancelled) {
          setLanAddress({
            host: null,
            api_url: null,
            frontend_url: null,
            qr_url: null,
            connect_page_url: null,
            qr_image_url: null,
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLanLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lanAddress, open]);

  const copyEmail = async () => {
    try {
      await navigator.clipboard.writeText(user.email);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };

  const copyLanAddress = async () => {
    if (!lanAddress?.api_url) return;
    try {
      await navigator.clipboard.writeText(lanAddress.api_url);
      setCopiedLan(true);
      setShowLanQr(true);
      window.setTimeout(() => setCopiedLan(false), 1200);
    } catch {
      setCopiedLan(false);
    }
  };

  const handleLogout = () => {
    setOpen(false);
    onLogout();
  };

  const saveDisplayName = async () => {
    const nextName = displayName.trim();
    if (!nextName) {
      setNameError("用户名不能为空");
      return;
    }
    if (nextName === user.display_name) {
      setEditingName(false);
      setNameError("");
      return;
    }
    setSavingName(true);
    setNameError("");
    try {
      const nextUser = await systemAuthApi.updateDisplayName(nextName);
      onUserChange(nextUser);
      setEditingName(false);
      setDisplayName(nextUser.display_name);
    } catch (err) {
      setNameError(err instanceof Error ? err.message : "用户名保存失败");
    } finally {
      setSavingName(false);
    }
  };

  return (
    <div className="user-menu" ref={menuRef}>
      <button
        type="button"
        className="user-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        title={user.display_name}
        onClick={() => {
          setDisplayName(user.display_name);
          setNameError("");
          setEditingName(false);
          setOpen((value) => !value);
        }}
      >
        {user.avatar_url ? (
          <Image
            src={user.avatar_url}
            alt={`${user.display_name} 的头像`}
            width={36}
            height={36}
            unoptimized
            className="user-menu-avatar"
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className="user-menu-initial">{initial}</span>
        )}
      </button>

      {open && (
        <div className="user-menu-popover" role="menu">
          <div className="user-menu-profile">
            <div className="user-menu-profile-avatar">
              {user.avatar_url ? (
                <Image
                  src={user.avatar_url}
                  alt={`${user.display_name} 的头像`}
                  width={42}
                  height={42}
                  unoptimized
                  className="user-menu-avatar"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="user-menu-initial">{initial}</span>
              )}
            </div>
            <div className="min-w-0">
              <div className="user-menu-eyebrow">当前账号</div>
              {editingName ? (
                <input
                  className="user-menu-name-input"
                  value={displayName}
                  autoFocus
                  maxLength={100}
                  onChange={(event) => setDisplayName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      void saveDisplayName();
                    }
                    if (event.key === "Escape") {
                      setEditingName(false);
                      setDisplayName(user.display_name);
                      setNameError("");
                    }
                  }}
                />
              ) : (
                <div className="user-menu-name">{user.display_name}</div>
              )}
              <div className="user-menu-email" title={user.email}>
                {user.email}
              </div>
              {nameError && <div className="user-menu-error">{nameError}</div>}
            </div>
          </div>

          <div className="user-menu-actions">
            <button
              type="button"
              className="user-menu-action"
              onClick={copyEmail}
            >
              <span>复制邮箱</span>
              <span className="user-menu-action-hint">
                {copied ? "已复制" : "Copy"}
              </span>
            </button>
            <button
              type="button"
              className="user-menu-action user-menu-lan-action"
              onClick={() => void copyLanAddress()}
              disabled={!lanAddress?.api_url}
              aria-label="复制电脑局域网地址"
            >
              <span className="user-menu-action-main">
                <span>电脑局域网地址</span>
                <span className="user-menu-action-value">
                  {lanLoading
                    ? "检测中..."
                    : lanAddress?.api_url || "未检测到局域网地址"}
                </span>
              </span>
              <span className="user-menu-action-hint">
                {copiedLan ? "已复制" : "Copy"}
              </span>
            </button>
            {editingName ? (
              <div className="user-menu-edit-actions">
                <button
                  type="button"
                  className="user-menu-action primary"
                  onClick={() => void saveDisplayName()}
                  disabled={savingName}
                >
                  <span>{savingName ? "保存中" : "保存用户名"}</span>
                </button>
                <button
                  type="button"
                  className="user-menu-action"
                  onClick={() => {
                    setEditingName(false);
                    setDisplayName(user.display_name);
                    setNameError("");
                  }}
                  disabled={savingName}
                >
                  <span>取消</span>
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="user-menu-action"
                onClick={() => {
                  setEditingName(true);
                  setDisplayName(user.display_name);
                  setNameError("");
                }}
              >
                <span>更改用户名</span>
                <span className="user-menu-action-hint">Edit</span>
              </button>
            )}
            {user.is_admin && onOpenAdmin && (
              <button
                type="button"
                className="user-menu-action"
                onClick={() => {
                  setOpen(false);
                  onOpenAdmin();
                }}
              >
                <span>用户管理</span>
                <span className="user-menu-action-hint">Admin</span>
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="user-menu-logout"
            role="menuitem"
          >
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            退出登录
          </button>
        </div>
      )}

      {showLanQr &&
        lanAddress?.api_url &&
        (lanAddress.qr_data_url ||
          lanAddress.qr_image_url ||
          lanAddress.qr_url) && (
          <div
            className="modal-backdrop"
            onMouseDown={() => setShowLanQr(false)}
          >
            <div
              className="modal-card local-connection-qr-card"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <div className="local-connection-qr-head">
                <div>
                  <div className="modal-title text-left">手机扫码连接</div>
                  <div className="modal-subtitle text-left">
                    打开手机端连接设置，点“扫码”识别这个二维码。
                  </div>
                </div>
                <button
                  type="button"
                  className="provider-config-close"
                  onClick={() => setShowLanQr(false)}
                  aria-label="关闭手机扫码连接"
                >
                  ×
                </button>
              </div>

              <Image
                className="local-connection-qr-image"
                src={
                  lanAddress.qr_data_url ||
                  lanAddress.qr_image_url ||
                  lanAddress.qr_url ||
                  ""
                }
                alt="手机连接二维码"
                width={220}
                height={220}
              />
              <div className="local-connection-qr-address">
                {lanAddress.api_url}
              </div>
            </div>
          </div>
        )}
    </div>
  );
}
