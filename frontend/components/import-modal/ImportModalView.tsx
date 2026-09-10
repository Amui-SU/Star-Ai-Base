import type {
  ImportMethod,
  QRCodeResponse,
  VideoMultiPartInfo,
} from "@/lib/api";
import type {
  ImportModalStep,
  ImportTaskProgressItem,
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
  multiPartInfo: VideoMultiPartInfo | null;
  qr: QRCodeResponse | null;
  qrErrorMessage: string;
  qrStatus: QRStatus;
  selectedPages: number[];
  step: ImportModalStep;
  taskProgress: ImportTaskProgressItem[];
  url: string;
  urlMessage: string;
  urlSubmitting: boolean;
  videoMode: VideoImportMode;
  onCancel: () => void;
  onCancelMultiPart: () => void;
  onGetQR: () => void;
  onLocalVideoFileChange: (file: File | null) => void;
  onOpenMethod: (method: ImportMethod) => void;
  onReturnToMethods: () => void;
  onSubmitLocalVideo: () => void;
  onSubmitMultiPart: () => void;
  onSubmitUrl: () => void;
  onSwitchVideoMode: (mode: VideoImportMode) => void;
  onTogglePage: (page: number) => void;
  onToggleAllPages: () => void;
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
  multiPartInfo,
  qr,
  qrErrorMessage,
  qrStatus,
  selectedPages,
  step,
  taskProgress,
  url,
  urlMessage,
  urlSubmitting,
  videoMode,
  onCancel,
  onCancelMultiPart,
  onGetQR,
  onLocalVideoFileChange,
  onOpenMethod,
  onReturnToMethods,
  onSubmitLocalVideo,
  onSubmitMultiPart,
  onSubmitUrl,
  onSwitchVideoMode,
  onTogglePage,
  onToggleAllPages,
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
          multiPartInfo={multiPartInfo}
          selectedPages={selectedPages}
          taskProgress={taskProgress}
          url={url}
          urlMessage={urlMessage}
          urlSubmitting={urlSubmitting}
          videoMode={videoMode}
          onCancel={onCancel}
          onCancelMultiPart={onCancelMultiPart}
          onLocalVideoFileChange={onLocalVideoFileChange}
          onSubmitLocalVideo={onSubmitLocalVideo}
          onSubmitMultiPart={onSubmitMultiPart}
          onSubmitUrl={onSubmitUrl}
          onSwitchVideoMode={onSwitchVideoMode}
          onTogglePage={onTogglePage}
          onToggleAllPages={onToggleAllPages}
          onUrlChange={onUrlChange}
        />
      )}
    </>
  );
}
