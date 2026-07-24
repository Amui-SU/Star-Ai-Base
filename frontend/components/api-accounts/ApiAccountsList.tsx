import { useEffect, useState } from "react";
import type { ApiAccount } from "@/lib/api";

interface ApiAccountsListProps {
  accounts: ApiAccount[];
  busyId: number | null;
  loading: boolean;
  onCreate: () => void;
  onEdit: (account: ApiAccount) => void;
  onRefresh: () => void;
  onRemove: (account: ApiAccount) => void;
  onSetDefault: (account: ApiAccount) => void;
  onValidate: (account: ApiAccount) => void;
}

export default function ApiAccountsList({
  accounts,
  busyId,
  loading,
  onCreate,
  onEdit,
  onRefresh,
  onRemove,
  onSetDefault,
  onValidate,
}: ApiAccountsListProps) {
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  useEffect(() => {
    const closeOutside = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (!target.closest(".api-account-menu-wrap")) setOpenMenuId(null);
    };
    document.addEventListener("mousedown", closeOutside);
    return () => document.removeEventListener("mousedown", closeOutside);
  }, []);

  const runAction = (action: () => void) => {
    setOpenMenuId(null);
    action();
  };

  return (
    <section className="api-accounts-list" aria-label="AI 服务密钥列表">
      <div className="api-accounts-toolbar">
        <span>{loading ? "加载中..." : `${accounts.length} 个密钥`}</span>
        <div className="api-accounts-toolbar-actions">
          <button
            type="button"
            className="admin-users-secondary"
            onClick={onRefresh}
            disabled={loading}
          >
            刷新
          </button>
          <button
            type="button"
            className="btn btn-primary"
            data-api-account-return="create"
            onClick={onCreate}
          >
            添加密钥
          </button>
        </div>
      </div>

      <div className="api-accounts-scroll">
        {accounts.length === 0 && !loading ? (
          <div className="api-accounts-empty">还没有 AI 服务密钥</div>
        ) : (
          <div className="api-accounts-grid">
            {accounts.map((account) => {
              const menuOpen = openMenuId === account.id;
              return (
                <article key={account.id} className="api-account-row">
                  <button
                    type="button"
                    className="api-account-main"
                    data-api-account-return={`account-${account.id}`}
                    onClick={() => onEdit(account)}
                  >
                    <span className="api-account-name">
                      {account.display_name}
                    </span>
                    <span className="api-account-meta">
                      {account.provider_label} / {account.model}
                    </span>
                  </button>
                  <div className="api-account-badges">
                    {account.is_default ? <span>默认</span> : null}
                    <span className={account.enabled ? "active" : "inactive"}>
                      {account.enabled ? "启用" : "停用"}
                    </span>
                    <span>{account.configured ? "已配置" : "未配置"}</span>
                  </div>
                  <div className="api-account-menu-wrap">
                    <button
                      type="button"
                      className="api-account-more"
                      aria-label={`更多操作 ${account.display_name}`}
                      aria-expanded={menuOpen}
                      onClick={() =>
                        setOpenMenuId((current) =>
                          current === account.id ? null : account.id,
                        )
                      }
                    >
                      ···
                    </button>
                    {menuOpen ? (
                      <div className="api-account-menu" role="menu">
                        <button
                          type="button"
                          disabled={account.is_default || busyId === account.id}
                          onClick={() => runAction(() => onSetDefault(account))}
                        >
                          设默认
                        </button>
                        <button
                          type="button"
                          disabled={busyId === account.id}
                          onClick={() => runAction(() => onValidate(account))}
                        >
                          验证
                        </button>
                        <button
                          type="button"
                          className="danger"
                          disabled={busyId === account.id}
                          onClick={() => runAction(() => onRemove(account))}
                        >
                          删除
                        </button>
                      </div>
                    ) : null}
                  </div>
                  {account.last_error ? (
                    <div className="api-account-error">
                      {account.last_error}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
