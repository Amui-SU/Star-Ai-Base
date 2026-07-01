"use client";

import Image from "next/image";
import ModalShell from "@/components/ui/ModalShell";
import type { LocalLanAddressResponse } from "@/lib/api";

interface UserMenuLanQrModalProps {
  lanAddress: LocalLanAddressResponse | null;
  open: boolean;
  onClose: () => void;
}

export default function UserMenuLanQrModal({
  lanAddress,
  open,
  onClose,
}: UserMenuLanQrModalProps) {
  const qrImage =
    lanAddress?.qr_data_url || lanAddress?.qr_image_url || lanAddress?.qr_url;

  if (!open || !lanAddress?.api_url || !qrImage) return null;

  return (
    <ModalShell cardClassName="local-connection-qr-card" onClose={onClose}>
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
          onClick={onClose}
          aria-label="关闭手机扫码连接"
        >
          ×
        </button>
      </div>

      <Image
        className="local-connection-qr-image"
        src={qrImage}
        alt="手机连接二维码"
        width={220}
        height={220}
      />
      <div className="local-connection-qr-address">{lanAddress.api_url}</div>
    </ModalShell>
  );
}
