"use client";

import ApiAccountsPanelView from "@/components/api-accounts/ApiAccountsPanelView";
import ApiAccountWorkspace from "@/components/api-accounts/ApiAccountWorkspace";
import { useApiAccountsPanel } from "@/components/api-accounts/useApiAccountsPanel";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

export default function ApiAccountsPanel({ open, onClose, onChanged }: Props) {
  const panel = useApiAccountsPanel({ open, onChanged });
  if (!open) return null;
  if (panel.view !== "list") {
    return (
      <ApiAccountWorkspace
        account={panel.selectedAccount}
        templates={panel.templates}
        onBack={panel.returnToList}
        onClose={onClose}
        onSaved={panel.workspaceSaved}
      />
    );
  }
  return (
    <ModalShell cardClassName="api-accounts-panel" onClose={onClose}>
      <ApiAccountsPanelView
        accounts={panel.accounts}
        busyId={panel.busyId}
        error={panel.error}
        loading={panel.loading}
        notice={panel.notice}
        onClose={onClose}
        onCreateAccount={panel.createAccount}
        onEditAccount={panel.editAccount}
        onRefreshAccounts={() => void panel.loadAccounts()}
        onRemoveAccount={(account) => void panel.removeAccount(account)}
        onSetDefault={(account) => void panel.setDefault(account)}
        onValidateAccount={(account) => void panel.validateAccount(account)}
      />
    </ModalShell>
  );
}
