"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiAccountApi, chatApi, type ApiAccount } from "@/lib/api";
import type { ApiAccountsPanelView, ThinkingTemplates } from "./types";

interface Params {
  open: boolean;
  onChanged?: () => void;
}

export function useApiAccountsPanel({ open, onChanged }: Params) {
  const [accounts, setAccounts] = useState<ApiAccount[]>([]);
  const [view, setView] = useState<ApiAccountsPanelView>("list");
  const [selectedAccount, setSelectedAccount] = useState<ApiAccount | null>(
    null,
  );
  const [templates, setTemplates] = useState<ThinkingTemplates>({});
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const returnFocusRef = useRef("create");

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      setAccounts(await apiAccountApi.list());
      return true;
    } catch (value) {
      setError(value instanceof Error ? value.message : "AI 服务密钥加载失败");
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const restoreListFocus = useCallback(() => {
    const key = returnFocusRef.current;
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>(`[data-api-account-return="${key}"]`)
        ?.focus();
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (cancelled) return;
      setView("list");
      setSelectedAccount(null);
      setError("");
      setNotice("");
      void loadAccounts();
      void chatApi
        .getModelConfig()
        .then((config) => {
          if (!cancelled)
            setTemplates(
              Object.fromEntries(
                config.providers.map((item) => [
                  item.provider,
                  item.thinking_template ?? {},
                ]),
              ),
            );
        })
        .catch(() => {
          if (!cancelled) setTemplates({});
        });
    });
    return () => {
      cancelled = true;
    };
  }, [loadAccounts, open]);

  const mutate = async (
    account: ApiAccount,
    action: "default" | "validate" | "remove",
  ) => {
    if (
      action === "remove" &&
      !window.confirm(`删除 ${account.display_name}？`)
    )
      return;
    setBusyId(account.id);
    setError("");
    try {
      if (action === "default") await apiAccountApi.setDefault(account.id);
      else if (action === "validate") await apiAccountApi.validate(account.id);
      else await apiAccountApi.remove(account.id);
      await loadAccounts();
      onChanged?.();
      setNotice(action === "remove" ? "密钥已删除" : "密钥状态已更新");
    } catch (value) {
      setError(value instanceof Error ? value.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  return {
    accounts,
    busyId,
    error,
    loading,
    notice,
    templates,
    view,
    selectedAccount,
    loadAccounts,
    createAccount: () => {
      returnFocusRef.current = "create";
      setSelectedAccount(null);
      setView("create");
    },
    editAccount: (account: ApiAccount) => {
      returnFocusRef.current = `account-${account.id}`;
      setSelectedAccount(account);
      setView("edit");
    },
    returnToList: () => {
      setView("list");
      setSelectedAccount(null);
      restoreListFocus();
    },
    workspaceSaved: async () => {
      onChanged?.();
      if (!(await loadAccounts()))
        throw new Error("密钥已保存，但列表刷新失败，请稍后返回列表刷新");
      setNotice("API 密钥已保存");
      setView("list");
      setSelectedAccount(null);
      restoreListFocus();
    },
    setDefault: (account: ApiAccount) => mutate(account, "default"),
    validateAccount: (account: ApiAccount) => mutate(account, "validate"),
    removeAccount: (account: ApiAccount) => mutate(account, "remove"),
  };
}
