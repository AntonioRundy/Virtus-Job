import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> User:
        existing = await self.db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ConflictException("Email already registered.")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            province=data.province,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedException("Account is deactivated.")

        user.last_login_at = datetime.now(timezone.utc)

        access_token = create_access_token(str(user.id))
        refresh_token_str = create_refresh_token(str(user.id))

        refresh_token = RefreshToken(
            token=refresh_token_str,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(refresh_token)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, token: str) -> TokenResponse:
        try:
            payload = decode_token(token)
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Invalid token type.")
            user_id = payload["sub"]
        except JWTError:
            raise UnauthorizedException("Token expired or invalid.")

        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == token,
                RefreshToken.revoked.is_(False),
            )
        )
        db_token = result.scalar_one_or_none()
        if not db_token:
            raise UnauthorizedException("Token not found or already revoked.")

        # Rotate: revoke old, issue new pair
        db_token.revoked = True
        new_access = create_access_token(user_id)
        new_refresh_str = create_refresh_token(user_id)

        new_refresh = RefreshToken(
            token=new_refresh_str,
            user_id=uuid.UUID(user_id),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(new_refresh)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, token: str) -> None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        db_token = result.scalar_one_or_none()
        if db_token:
            db_token.revoked = True
