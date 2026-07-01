"use client";

import Image from "next/image";
import UserMenuLanQrModal from "@/components/user-menu/UserMenuLanQrModal";
import { useUserMenuState } from "@/components/user-menu/useUserMenuState";
import type { SystemUser } from "@/lib/api";

interface Props {
  user: SystemUser;
  onUserChange: (user: SystemUser) => void;
  onLogout: () => void;
  onOpenApiAccounts?: () => void;
  onOpenAdmin?: () => void;
}

export default function UserMenu({
  user,
  onUserChange,
  onLogout,
  onOpenApiAccounts,
  onOpenAdmin,
}: Props) {
  const {
    cancelEditingName,
    closeLanQr,
    copied,
    copiedLan,
    copyEmail,
    copyLanAddress,
    displayName,
    editingName,
    handleLogout,
    handleNameKeyDown,
    initial,
    lanAddress,
    lanLoading,
    menuRef,
    nameError,
    open,
    openAdmin,
    openApiAccounts,
    saveDisplayName,
    savingName,
    setDisplayName,
    showLanQr,
    startEditingName,
    toggleOpen,
  } = useUserMenuState({
    user,
    onUserChange,
    onLogout,
    onOpenApiAccounts,
    onOpenAdmin,
  });

  return (
    <div className="user-menu" ref={menuRef}>
      <button
        type="button"
        className="user-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        title={user.display_name}
        onClick={toggleOpen}
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
                  onKeyDown={handleNameKeyDown}
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
                  onClick={cancelEditingName}
                  disabled={savingName}
                >
                  <span>取消</span>
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="user-menu-action"
                onClick={startEditingName}
              >
                <span>更改用户名</span>
                <span className="user-menu-action-hint">Edit</span>
              </button>
            )}
            {onOpenApiAccounts && (
              <button
                type="button"
                className="user-menu-action"
                onClick={openApiAccounts}
              >
                <span>AI 服务密钥</span>
                <span className="user-menu-action-hint">Keys</span>
              </button>
            )}
            {user.is_admin && onOpenAdmin && (
              <button
                type="button"
                className="user-menu-action"
                onClick={openAdmin}
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

      <UserMenuLanQrModal
        open={showLanQr}
        lanAddress={lanAddress}
        onClose={closeLanQr}
      />
    </div>
  );
}
