import {
  BarcodeFormat,
  BarcodeScanner,
} from "@capacitor-mlkit/barcode-scanning";
import { parseLocalConnectionUrl } from "@/lib/localConnection";

type PermissionState = "granted" | "limited" | "denied" | "prompt" | string;

function hasCameraPermission(camera: PermissionState | undefined): boolean {
  return camera === "granted" || camera === "limited";
}

export async function scanLocalConnectionQrCode(): Promise<string> {
  const permission = await BarcodeScanner.requestPermissions();
  if (!hasCameraPermission(permission.camera)) {
    throw new Error("需要相机权限才能扫码");
  }

  const result = await BarcodeScanner.scan({
    formats: [BarcodeFormat.QrCode],
  });

  for (const barcode of result.barcodes) {
    const value = barcode.rawValue || barcode.displayValue || "";
    const apiBaseUrl = parseLocalConnectionUrl(value);
    if (apiBaseUrl) return apiBaseUrl;
  }

  throw new Error("未识别到智库云连接二维码");
}
