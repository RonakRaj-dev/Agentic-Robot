import os
import time
import jwt
from typing import Optional, Dict, Any, List
from loguru import logger
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class AuthService:
    """
    JWT Authentication & Role-Based Access Control (RBAC) Service.
    Signs and validates HMAC-SHA256 (HS256) JWT access tokens.
    """
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256", token_expire_seconds: int = 86400) -> None:
        self.secret_key = secret_key or os.environ.get("JWT_SECRET_KEY", "edubot_super_secret_jwt_key_2026!")
        self.algorithm = algorithm
        self.token_expire_seconds = token_expire_seconds
        self.security = HTTPBearer(auto_error=False)

    def create_access_token(self, username: str, role: str = "student", class_level: int = 6, user_id: Optional[str] = None) -> str:
        now = int(time.time())
        payload = {
            "sub": username,
            "user_id": user_id,
            "role": role,
            "class_level": class_level,
            "type": "access",
            "iat": now,
            "exp": now + self.token_expire_seconds,
            "iss": "edubot_auth_service"
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, username: str, role: str = "student", class_level: int = 6, user_id: Optional[str] = None) -> str:
        now = int(time.time())
        payload = {
            "sub": username,
            "user_id": user_id,
            "role": role,
            "class_level": class_level,
            "type": "refresh",
            "iat": now,
            "exp": now + (7 * 86400),  # 7 days lifetime
            "iss": "edubot_auth_service"
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], issuer="edubot_auth_service")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid authentication token: {str(e)}")

    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        payload = self.verify_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type: Refresh token required.")
        return payload

auth_service = AuthService()

async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency for optional JWT verification."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # Check query parameter fallback
        token = request.query_params.get("token")
        if not token:
            return None
    else:
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        token = parts[1]

    try:
        return auth_service.verify_token(token)
    except Exception:
        return None

async def get_current_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency enforcing valid JWT token."""
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing or invalid Bearer JWT token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

def require_roles(allowed_roles: List[str]):
    """FastAPI RBAC dependency verifying user possesses required role."""
    async def role_checker(user: Dict[str, Any] = Security(get_current_user)) -> Dict[str, Any]:
        user_role = user.get("role", "student")
        if user_role not in allowed_roles:
            logger.warning(f"Access denied for user '{user.get('sub')}': Role '{user_role}' not in allowed roles {allowed_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Access requires one of the following roles: {allowed_roles}"
            )
        return user
    return role_checker
