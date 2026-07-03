import type { ImportMethod, QRCodeResponse } from "@/lib/api";
import type {
  ImportModalStep,
  VideoImportMode,
} from "@/components/import-modal/useImportModal";
import ImportBilibiliStep from "@/components/import-modal/ImportBilibiliStep";
import ImportMethodGrid from "@/components/import-modal/ImportMethodGrid";
import ImportVideoStep from "@/components/import-modal/ImportVideoStep";

type QRStatus = "idle" | "loading" | "ready" | "scanned" | "success" | "error";

interface ImportModalViewProps {
  hasBilibiliBinding: boolean;
  knowledgeBaseId?: number | null;
  localVideoFile: File | null;
  localVideoMessage: string;
  localVideoSubmitting: boolean;
  methodList: ImportMethod[];
  qr: QRCodeResponse | null;
  qrErrorMessage: string;
  qrStatus: QRStatus;
  step: ImportModalStep;
  url: string;
  urlMessage: string;
  urlSubmitting: boolean;
  videoMode: VideoImportMode;
  onCancel: () => void;
  onGetQR: () => void;
  onLocalVideoFileChange: (file: File | null) => void;
  onOpenMethod: (method: ImportMethod) => void;
  onReturnToMethods: () => void;
  onSubmitLocalVideo: () => void;
  onSubmitUrl: () => void;
  onSwitchVideoMode: (mode: VideoImportMode) => void;
  onUrlChange: (value: string) => void;
}

function titleForStep(step: ImportModalStep): string {
  if (step === "methods") return "导入资料";
  if (step === "bilibili") return "B 站收藏夹";
  return "导入视频";
}

export default function ImportModalView({
  hasBilibiliBinding,
  knowledgeBaseId,
  localVideoFile,
  localVideoMessage,
  localVideoSubmitting,
  methodList,
  qr,
  qrErrorMessage,
  qrStatus,
  step,
  url,
  urlMessage,
  urlSubmitting,
  videoMode,
  onCancel,
  onGetQR,
  onLocalVideoFileChange,
  onOpenMethod,
  onReturnToMethods,
  onSubmitLocalVideo,
  onSubmitUrl,
  onSwitchVideoMode,
  onUrlChange,
}: ImportModalViewProps) {
  return (
    <>
      <div className="import-modal-head">
        <div>
          <div className="modal-title text-left">{titleForStep(step)}</div>
          <div className="modal-subtitle text-left">
            选择导入方式，资料会进入当前知识库
          </div>
        </div>
        {step !== "methods" && (
          <button
            type="button"
            className="import-back-btn"
            onClick={onReturnToMethods}
          >
            返回
          </button>
        )}
      </div>

      {step === "methods" && (
        <ImportMethodGrid methods={methodList} onOpenMethod={onOpenMethod} />
      )}

      {step === "bilibili" && (
        <ImportBilibiliStep
          hasBilibiliBinding={hasBilibiliBinding}
          qr={qr}
          qrErrorMessage={qrErrorMessage}
          qrStatus={qrStatus}
          onRetryQR={onGetQR}
        />
      )}

      {step === "video" && (
        <ImportVideoStep
          knowledgeBaseId={knowledgeBaseId}
          localVideoFile={localVideoFile}
          localVideoMessage={localVideoMessage}
          localVideoSubmitting={localVideoSubmitting}
          url={url}
          urlMessage={urlMessage}
          urlSubmitting={urlSubmitting}
          videoMode={videoMode}
          onCancel={onCancel}
          onLocalVideoFileChange={onLocalVideoFileChange}
          onSubmitLocalVideo={onSubmitLocalVideo}
          onSubmitUrl={onSubmitUrl}
          onSwitchVideoMode={onSwitchVideoMode}
          onUrlChange={onUrlChange}
        />
      )}
    </>
  );
}
