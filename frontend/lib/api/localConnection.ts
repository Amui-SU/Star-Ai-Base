import { request } from "./client";
import type { LocalLanAddressResponse } from "./localConnectionTypes";

export const localConnectionApi = {
  lanAddress: () =>
    request<LocalLanAddressResponse>("/local-connection/lan-address"),
};
