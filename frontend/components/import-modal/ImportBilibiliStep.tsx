import Image from "next/image";

import type { QRCodeResponse } from "@/lib/api";

type QRStatus = "idle" | "loading" | "ready" | "scanned" | "success" | "error";

interface ImportBilibiliStepProps {
  hasBilibiliBinding: boolean;
  qr: QRCodeResponse | null;
  qrErrorMessage: string;
  qrStatus: QRStatus;
  onRetryQR: () => void;
}

export default function ImportBilibiliStep({
  hasBilibiliBinding,
  qr,
  qrErrorMessage,
  qrStatus,
  onRetryQR,
}: ImportBilibiliStepProps) {
  return (
    <div className="import-step-body">
      {hasBilibiliBinding ? (
        <div className="import-bound-card">
          <div className="status-pill ok">已绑定</div>
          <p>B 站收藏夹已可在左侧列表中选择并入库。</p>
        </div>
      ) : (
        <>
          <p className="import-step-copy">
            使用哔哩哔哩 APP 扫码绑定账号，绑定完成后会显示收藏夹资料。
          </p>
          <div className="import-qr-wrap">
            {qrStatus === "loading" && (
              <div className="import-qr-placeholder">
                <div className="w-8 h-8 border-2 border-(--accent) border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            {(qrStatus === "ready" || qrStatus === "scanned") && qr && (
              <div className="relative">
                <Image
                  src={qr.qrcode_image_base64}
                  alt="B站绑定二维码"
                  width={192}
                  height={192}
                  unoptimized
                  className="import-qr-image"
                />
                {qrStatus === "scanned" && (
                  <div className="import-qr-overlay">
                    <div className="status-pill">已扫码</div>
                    <span>请在手机上确认</span>
                  </div>
                )}
              </div>
            )}
            {qrStatus === "success" && (
              <div className="import-qr-placeholder">
                <div className="status-pill ok">绑定成功</div>
              </div>
            )}
            {qrStatus === "error" && (
              <div className="import-qr-placeholder">
                <p>{qrErrorMessage}</p>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={onRetryQR}
                >
                  重新获取
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
