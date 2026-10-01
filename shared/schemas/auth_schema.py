from uuid import UUID
from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional

from shared.security.password_policy import validate_password_strength


class RegisterRequest(BaseModel):
    email: EmailStr
    first_name: Optional[str] = ""  # optional field
    last_name: Optional[str] = ""  # optional field
    password: str
    # Unticked by default — GDPR requires an affirmative opt-in, not a
    # pre-checked box. Marketing consent is optional and separate.
    consent_data_processing: bool = False
    consent_marketing: bool = False

    @model_validator(mode="after")
    def _check_password_strength(self):
        validate_password_strength(
            self.password,
            email=self.email,
            name=f"{self.first_name or ''} {self.last_name or ''}".strip(),
        )
        return self

    @model_validator(mode="after")
    def _check_consent(self):
        if not self.consent_data_processing:
            raise ValueError("Consent to data processing is required to register")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    status: str


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr


class ImpersonateRequest(BaseModel):
    customer_id: UUID


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer_id: UUID
    customer_name: str
    expires_in: int


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str


class VerifyEmailResponse(TokenResponse):
    # Verification is now the first point identity is confirmed, so it
    # issues the account's first session — same shape as TokenResponse.
    email_verified: bool


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ResendVerificationResponse(BaseModel):
    sent: bool
    # Only populated when EXPOSE_VERIFICATION_TOKEN_FOR_TESTS is set
    # (local/e2e envs only) — lets e2e drive the real verify-email flow
    # without a real inbox. Always None in production.
    debug_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    sent: bool
    # Same test-only escape hatch as ResendVerificationResponse.debug_token.
    debug_token: str | None = None


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    reset: bool
