"use client";

import ImportModalView from "@/components/import-modal/ImportModalView";
import { useImportModal } from "@/components/import-modal/useImportModal";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  knowledgeBaseId?: number | null;
  hasBilibiliBinding: boolean;
  onClose: () => void;
  onBound: () => void;
  onImported?: () => void;
}

export default function ImportModal({
  open,
  knowledgeBaseId,
  hasBilibiliBinding,
  onClose,
  onBound,
  onImported,
}: Props) {
  const {
    getQR,
    localVideoFile,
    localVideoMessage,
    localVideoSubmitting,
    methodList,
    openMethod,
    qr,
    qrErrorMessage,
    qrStatus,
    returnToMethods,
    setLocalVideoFile,
    setUrl,
    step,
    submitLocalVideo,
    submitUrl,
    switchVideoMode,
    url,
    urlMessage,
    urlSubmitting,
    videoMode,
  } = useImportModal({
    hasBilibiliBinding,
    knowledgeBaseId,
    onBound,
    onClose,
    onImported,
    open,
  });

  if (!open) return null;

  return (
    <ModalShell
      cardClassName={`import-modal ${
        step === "methods" ? "import-modal-methods" : "import-modal-step"
      }`}
      onClose={onClose}
    >
      <ImportModalView
        hasBilibiliBinding={hasBilibiliBinding}
        knowledgeBaseId={knowledgeBaseId}
        localVideoFile={localVideoFile}
        localVideoMessage={localVideoMessage}
        localVideoSubmitting={localVideoSubmitting}
        methodList={methodList}
        qr={qr}
        qrErrorMessage={qrErrorMessage}
        qrStatus={qrStatus}
        step={step}
        url={url}
        urlMessage={urlMessage}
        urlSubmitting={urlSubmitting}
        videoMode={videoMode}
        onCancel={onClose}
        onGetQR={() => void getQR()}
        onLocalVideoFileChange={setLocalVideoFile}
        onOpenMethod={openMethod}
        onReturnToMethods={returnToMethods}
        onSubmitLocalVideo={() => void submitLocalVideo()}
        onSubmitUrl={() => void submitUrl()}
        onSwitchVideoMode={switchVideoMode}
        onUrlChange={setUrl}
      />
    </ModalShell>
  );
}
