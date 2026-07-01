"use client";

import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import {
  localConnectionApi,
  type LocalLanAddressResponse,
  systemAuthApi,
  type SystemUser,
} from "@/lib/api";

interface UseUserMenuStateOptions {
  user: SystemUser;
  onUserChange: (user: SystemUser) => void;
  onLogout: () => void;
  onOpenApiAccounts?: () => void;
  onOpenAdmin?: () => void;
}

const unavailableLanAddress: LocalLanAddressResponse = {
  host: null,
  api_url: null,
  frontend_url: null,
  qr_url: null,
  connect_page_url: null,
  qr_image_url: null,
  qr_data_url: null,
};

export function useUserMenuState({
  user,
  onUserChange,
  onLogout,
  onOpenApiAccounts,
  onOpenAdmin,
}: UseUserMenuStateOptions) {
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
        if (!cancelled) setLanAddress(unavailableLanAddress);
      })
      .finally(() => {
        if (!cancelled) setLanLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lanAddress, open]);

  const resetNameEditor = () => {
    setDisplayName(user.display_name);
    setNameError("");
    setEditingName(false);
  };

  const toggleOpen = () => {
    resetNameEditor();
    setOpen((value) => !value);
  };

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
    } catch (error) {
      setNameError(error instanceof Error ? error.message : "用户名保存失败");
    } finally {
      setSavingName(false);
    }
  };

  const startEditingName = () => {
    setEditingName(true);
    setDisplayName(user.display_name);
    setNameError("");
  };

  const cancelEditingName = () => {
    setEditingName(false);
    setDisplayName(user.display_name);
    setNameError("");
  };

  const handleNameKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      void saveDisplayName();
    }
    if (event.key === "Escape") {
      cancelEditingName();
    }
  };

  const openApiAccounts = () => {
    setOpen(false);
    onOpenApiAccounts?.();
  };

  const openAdmin = () => {
    setOpen(false);
    onOpenAdmin?.();
  };

  return {
    copied,
    copiedLan,
    displayName,
    editingName,
    initial,
    lanAddress,
    lanLoading,
    menuRef,
    nameError,
    open,
    savingName,
    showLanQr,
    cancelEditingName,
    closeLanQr: () => setShowLanQr(false),
    copyEmail,
    copyLanAddress,
    handleLogout,
    handleNameKeyDown,
    openAdmin,
    openApiAccounts,
    saveDisplayName,
    setDisplayName,
    startEditingName,
    toggleOpen,
  };
}
