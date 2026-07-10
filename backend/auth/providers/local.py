from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.providers.base import IdentityProviderAdapter
from auth.schemas import AuthenticatedIdentity
from models.auth import IdentityProvider, UserAccount


class LocalPasswordService:
    MIN_LENGTH = 14

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self.hasher = hasher or PasswordHasher()
        # A stable dummy hash keeps the missing-user path computationally similar to
        # a real password verification without exposing any valid credential.
        self._dummy_hash = self.hasher.hash("agenticops-dummy-password-never-valid")

    def validate_new_password(self, password: str) -> None:
        if len(password) < self.MIN_LENGTH:
            raise ValueError(f"local password must contain at least {self.MIN_LENGTH} characters")
        if password.strip() != password:
            raise ValueError("local password must not start or end with whitespace")

    def hash_password(self, password: str) -> str:
        self.validate_new_password(password)
        return self.hasher.hash(password)

    def verify_password(self, password_hash: str | None, password: str) -> bool:
        candidate_hash = password_hash or self._dummy_hash
        try:
            verified = bool(self.hasher.verify(candidate_hash, password))
            return verified and password_hash is not None
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return self.hasher.check_needs_rehash(password_hash)


class LocalIdentityProvider(IdentityProviderAdapter):
    provider_type = "local"

    def __init__(self, passwords: LocalPasswordService | None = None) -> None:
        self.passwords = passwords or LocalPasswordService()

    async def authenticate_credentials(
        self,
        db: Session,
        provider: IdentityProvider,
        *,
        username: str,
        password: str,
    ) -> AuthenticatedIdentity | None:
        normalized_username = username.strip().lower()
        user = (
            db.query(UserAccount)
            .filter(func.lower(UserAccount.username) == normalized_username)
            .first()
        )
        password_hash = user.password_hash if user and user.active else None
        if not self.passwords.verify_password(password_hash, password):
            return None
        assert user is not None
        return AuthenticatedIdentity(
            provider_key=provider.provider_key,
            subject=f"local:{user.id}",
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            claims={"user_id": int(user.id), "is_emergency": bool(user.is_emergency)},
        )
