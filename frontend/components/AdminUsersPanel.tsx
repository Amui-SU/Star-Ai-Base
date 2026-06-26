"use client";

import { useEffect, useState } from "react";
import { systemAuthApi, type AdminUser } from "@/lib/api";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  currentUserId: number;
  onClose: () => void;
}

export default function AdminUsersPanel({
  open,
  currentUserId,
  onClose,
}: Props) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyUserId, setBusyUserId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [temporaryPassword, setTemporaryPassword] = useState<{
    email: string;
    value: string;
  } | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const nextUsers = await systemAuthApi.adminListUsers();
      setUsers(nextUsers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "用户列表加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) void loadUsers();
    });
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const updateStatus = async (user: AdminUser) => {
    const nextStatus = user.status === "active" ? "inactive" : "active";
    setBusyUserId(user.id);
    setError("");
    try {
      await systemAuthApi.adminUpdateUserStatus(user.id, nextStatus);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "用户状态更新失败");
    } finally {
      setBusyUserId(null);
    }
  };

  const resetPassword = async (user: AdminUser) => {
    setBusyUserId(user.id);
    setError("");
    setTemporaryPassword(null);
    try {
      const response = await systemAuthApi.adminResetUserPassword(user.id);
      setTemporaryPassword({
        email: response.user.email,
        value: response.temporary_password,
      });
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "密码重置失败");
    } finally {
      setBusyUserId(null);
    }
  };

  const copyTemporaryPassword = async () => {
    if (!temporaryPassword) return;
    try {
      await navigator.clipboard?.writeText(temporaryPassword.value);
    } catch {
      // The password remains visible if clipboard access is unavailable.
    }
  };

  return (
    <ModalShell cardClassName="admin-users-panel" onClose={onClose}>
      <div className="provider-config-head">
        <div className="provider-config-title-block">
          <div className="provider-config-title">用户管理</div>
          <div className="provider-config-subtitle">
            查看本机后端账号，启用/禁用用户，或生成临时密码。
          </div>
        </div>
        <button
          type="button"
          className="provider-config-close"
          onClick={onClose}
          aria-label="关闭用户管理"
        >
          ×
        </button>
      </div>

      <div className="admin-users-toolbar">
        <div className="admin-users-count">
          {loading ? "加载中..." : `${users.length} 个账号`}
        </div>
        <button
          type="button"
          className="admin-users-secondary"
          onClick={() => void loadUsers()}
          disabled={loading}
        >
          刷新
        </button>
      </div>

      {error && <div className="admin-users-error">{error}</div>}

      {temporaryPassword && (
        <div className="admin-users-password-card">
          <div>
            <div className="admin-users-password-label">临时密码</div>
            <div className="admin-users-password-email">
              {temporaryPassword.email}
            </div>
          </div>
          <code>{temporaryPassword.value}</code>
          <button
            type="button"
            className="admin-users-secondary"
            onClick={() => void copyTemporaryPassword()}
          >
            Copy
          </button>
        </div>
      )}

      <div className="admin-users-list">
        {users.map((user) => {
          const isSelf = user.id === currentUserId;
          const isBusy = busyUserId === user.id;
          const isActive = user.status === "active";
          return (
            <div className="admin-users-row" key={user.id}>
              <div className="admin-users-main">
                <div className="admin-users-name">{user.display_name}</div>
                <div className="admin-users-email">{user.email}</div>
              </div>
              <div className="admin-users-badges">
                {user.is_admin && <span>管理员</span>}
                <span className={isActive ? "active" : "inactive"}>
                  {isActive ? "启用" : "禁用"}
                </span>
              </div>
              <div className="admin-users-actions">
                <button
                  type="button"
                  className="admin-users-secondary"
                  onClick={() => void updateStatus(user)}
                  disabled={isSelf || isBusy}
                  aria-label={`${isActive ? "禁用" : "启用"} ${user.email}`}
                >
                  {isActive ? "禁用" : "启用"}
                </button>
                <button
                  type="button"
                  className="admin-users-primary"
                  onClick={() => void resetPassword(user)}
                  disabled={isSelf || isBusy}
                  aria-label={`重置 ${user.email} 的密码`}
                >
                  重置密码
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ModalShell>
  );
}
