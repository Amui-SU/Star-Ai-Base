"""External source binding API schemas."""

from typing import Optional

from pydantic import BaseModel


class SourceBindingResponse(BaseModel):
    id: int
    source_type: str
    external_account_id: str
    external_account_name: Optional[str] = None
    external_avatar_url: Optional[str] = None
    status: str


class QRCodeResponse(BaseModel):
    """QR code binding/login response."""

    qrcode_key: str
    qrcode_url: str
    qrcode_image_base64: str


class LoginStatusResponse(BaseModel):
    """QR code binding/login polling response."""

    status: str
    message: str
    user_info: Optional[dict] = None
    session_id: Optional[str] = None
