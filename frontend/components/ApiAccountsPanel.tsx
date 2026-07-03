"use client";

import ApiAccountsPanelView from "@/components/api-accounts/ApiAccountsPanelView";
import { useApiAccountsPanel } from "@/components/api-accounts/useApiAccountsPanel";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

export default function ApiAccountsPanel({ open, onClose, onChanged }: Props) {
  const {
    accounts,
    busyId,
    editAccount,
    editing,
    error,
    form,
    isSearchProvider,
    loadAccounts,
    loading,
    notice,
    removeAccount,
    resetForm,
    saveAccount,
    saving,
    selectedPreset,
    selectProvider,
    setDefault,
    setForm,
    validateAccount,
  } = useApiAccountsPanel({ open, onChanged });

  if (!open) return null;

  return (
    <ModalShell cardClassName="api-accounts-panel" onClose={onClose}>
      <ApiAccountsPanelView
        accounts={accounts}
        busyId={busyId}
        editing={editing}
        error={error}
        form={form}
        isSearchProvider={isSearchProvider}
        loading={loading}
        notice={notice}
        saving={saving}
        selectedPreset={selectedPreset}
        setForm={setForm}
        onClose={onClose}
        onEditAccount={editAccount}
        onRefreshAccounts={() => void loadAccounts()}
        onRemoveAccount={(account) => void removeAccount(account)}
        onResetForm={resetForm}
        onSaveAccount={() => void saveAccount()}
        onSelectProvider={selectProvider}
        onSetDefault={(account) => void setDefault(account)}
        onValidateAccount={(account) => void validateAccount(account)}
      />
    </ModalShell>
  );
}
