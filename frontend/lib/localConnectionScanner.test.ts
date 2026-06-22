import { afterEach, describe, expect, it, vi } from "vitest";

import { parseLocalConnectionUrl } from "@/lib/localConnection";

const scan = vi.fn();
const requestPermissions = vi.fn();

vi.mock("@capacitor-mlkit/barcode-scanning", () => ({
  BarcodeFormat: {
    QrCode: "QR_CODE",
  },
  BarcodeScanner: {
    requestPermissions,
    scan,
  },
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe("local connection QR scanner", () => {
  it("scans a QR code deep link and returns the backend API URL", async () => {
    requestPermissions.mockResolvedValue({ camera: "granted" });
    scan.mockResolvedValue({
      barcodes: [
        {
          rawValue: "zhikuyun://connect?api=http%3A%2F%2F192.168.1.200%3A8000",
        },
      ],
    });
    const { scanLocalConnectionQrCode } =
      await import("./localConnectionScanner");

    await expect(scanLocalConnectionQrCode()).resolves.toBe(
      "http://192.168.1.200:8000",
    );
    expect(requestPermissions).toHaveBeenCalledOnce();
    expect(scan).toHaveBeenCalledWith({ formats: ["QR_CODE"] });
  });

  it("scans a QR image URL and returns the backend API URL", async () => {
    requestPermissions.mockResolvedValue({ camera: "granted" });
    scan.mockResolvedValue({
      barcodes: [
        {
          rawValue:
            "http://192.168.1.200:8000/local-connection/mobile-connect.png?api=http%3A%2F%2F192.168.1.200%3A8000",
        },
      ],
    });
    const { scanLocalConnectionQrCode } =
      await import("./localConnectionScanner");

    await expect(scanLocalConnectionQrCode()).resolves.toBe(
      "http://192.168.1.200:8000",
    );
  });

  it("rejects unrecognized QR code contents", async () => {
    requestPermissions.mockResolvedValue({ camera: "granted" });
    scan.mockResolvedValue({ barcodes: [{ rawValue: "hello" }] });
    const { scanLocalConnectionQrCode } =
      await import("./localConnectionScanner");

    await expect(scanLocalConnectionQrCode()).rejects.toThrow(
      "未识别到智库云连接二维码",
    );
  });
});

describe("parseLocalConnectionUrl", () => {
  it("keeps QR deep links compatible with the scanner", () => {
    expect(
      parseLocalConnectionUrl(
        "zhikuyun://connect?api=http%3A%2F%2F192.168.1.200%3A8000",
      ),
    ).toBe("http://192.168.1.200:8000");
  });
});
