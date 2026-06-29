export interface LocalLanAddressResponse {
  host: string | null;
  api_url: string | null;
  frontend_url: string | null;
  qr_url: string | null;
  connect_page_url?: string | null;
  qr_image_url?: string | null;
  qr_data_url?: string | null;
}
