import type { ApiAccount } from "@/lib/api";

interface ApiAccountsListProps {
  accounts: ApiAccount[];
  busyId: number | null;
  formAccountId: number | null;
  loading: boolean;
  onEdit: (account: ApiAccount) => void;
  onRefresh: () => void;
  onRemove: (account: ApiAccount) => void;
  onSetDefault: (account: ApiAccount) => void;
  onValidate: (account: ApiAccount) => void;
}

export default function ApiAccountsList({
  accounts,
  busyId,
  formAccountId,
  loading,
  onEdit,
  onRefresh,
  onRemove,
  onSetDefault,
  onValidate,
}: ApiAccountsListProps) {
  return (
    <section className="api-accounts-list" aria-label="AI 服务密钥列表">
      <div className="api-accounts-toolbar">
        <span>{loading ? "加载中..." : `${accounts.length} 个密钥`}</span>
        <button
          type="button"
          className="admin-users-secondary"
          onClick={onRefresh}
          disabled={loading}
        >
          刷新
        </button>
      </div>

      {accounts.length === 0 && !loading ? (
        <div className="api-accounts-empty">还没有 AI 服务密钥</div>
      ) : (
        accounts.map((account) => (
          <article
            key={account.id}
            className={`api-account-row ${
              formAccountId === account.id ? "active" : ""
            }`}
          >
            <button
              type="button"
              className="api-account-main"
              onClick={() => onEdit(account)}
            >
              <span className="api-account-name">{account.display_name}</span>
              <span className="api-account-meta">
                {account.provider_label} / {account.model}
              </span>
            </button>
            <div className="api-account-badges">
              {account.is_default && <span>默认</span>}
              <span className={account.enabled ? "active" : "inactive"}>
                {account.enabled ? "启用" : "停用"}
              </span>
            </div>
            <div className="api-account-actions">
              <button
                type="button"
                className="admin-users-secondary"
                onClick={() => onSetDefault(account)}
                disabled={account.is_default || busyId === account.id}
              >
                设默认
              </button>
              <button
                type="button"
                className="admin-users-secondary"
                onClick={() => onValidate(account)}
                disabled={busyId === account.id}
              >
                验证
              </button>
              <button
                type="button"
                className="admin-users-secondary danger"
                onClick={() => onRemove(account)}
                disabled={busyId === account.id}
              >
                删除
              </button>
            </div>
            {account.last_error && (
              <div className="api-account-error">{account.last_error}</div>
            )}
          </article>
        ))
      )}
    </section>
  );
}
