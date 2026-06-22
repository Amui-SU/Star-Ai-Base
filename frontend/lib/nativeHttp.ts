import { Capacitor, CapacitorHttp } from "@capacitor/core";

function canUseNativeHttp(): boolean {
  return (
    typeof window !== "undefined" &&
    Capacitor.isNativePlatform() &&
    typeof CapacitorHttp?.request === "function"
  );
}

function headersToRecord(headers?: HeadersInit): Record<string, string> {
  const result: Record<string, string> = {};
  if (!headers) return result;
  new Headers(headers).forEach((value, key) => {
    result[key] = value;
  });
  return result;
}

function getHeaderValue(
  headers: Record<string, string>,
  name: string,
): string | undefined {
  const expected = name.toLowerCase();
  const key = Object.keys(headers).find(
    (item) => item.toLowerCase() === expected,
  );
  return key ? headers[key] : undefined;
}

function isFormDataBody(body: BodyInit | null | undefined): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const data = String(reader.result || "");
      resolve(data.includes(",") ? data.split(",").pop() || "" : data);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function formDataToNativeData(formData: FormData) {
  const nativeData = [];
  for (const [key, value] of formData.entries()) {
    if (value instanceof File) {
      nativeData.push({
        key,
        value: await readFileAsBase64(value),
        type: "base64File",
        contentType: value.type,
        fileName: value.name,
      });
    } else {
      nativeData.push({ key, value, type: "string" });
    }
  }
  return nativeData;
}

async function bodyToNativeData(
  body: BodyInit | null | undefined,
  headers: Record<string, string>,
): Promise<unknown> {
  if (body == null) return undefined;
  if (typeof body === "string") {
    const contentType = getHeaderValue(headers, "content-type") || "";
    if (contentType.toLowerCase().includes("application/json")) {
      try {
        return JSON.parse(body);
      } catch {
        return body;
      }
    }
    return body;
  }
  if (body instanceof URLSearchParams) return body.toString();
  if (isFormDataBody(body)) return formDataToNativeData(body);
  throw new Error("Native HTTP fallback only supports string request bodies.");
}

function nativeDataToBody(data: unknown): BodyInit | null {
  if (data == null) return null;
  if (typeof data === "string") return data;
  return JSON.stringify(data);
}

async function requestWithNativeHttp(
  url: string,
  init: RequestInit,
): Promise<Response> {
  const headers = headersToRecord(init.headers);
  const nativeResponse = await CapacitorHttp.request({
    url,
    method: init.method || "GET",
    headers,
    data: await bodyToNativeData(init.body, headers),
    ...(isFormDataBody(init.body) ? { dataType: "formData" as const } : {}),
    connectTimeout: 8000,
    readTimeout: 15000,
  });

  return new Response(nativeDataToBody(nativeResponse.data), {
    status: nativeResponse.status,
    headers: nativeResponse.headers,
  });
}

export async function requestWithNativeFallback(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (fetchError) {
    if (!canUseNativeHttp()) throw fetchError;
    const url = typeof input === "string" ? input : input.toString();
    try {
      return await requestWithNativeHttp(url, init);
    } catch (nativeError) {
      throw new Error(
        nativeError instanceof Error
          ? nativeError.message
          : "Native HTTP failed",
        { cause: nativeError },
      );
    }
  }
}
