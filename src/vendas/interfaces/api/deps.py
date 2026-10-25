from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vendas.domain.ports.auth import AuthContext, AuthPort, Role

security = HTTPBearer(auto_error=False)
security_dep = Security(security)


async def get_auth_port(request: Request) -> AuthPort:
    auth_port = getattr(request.app.state, "auth_port", None)
    if auth_port is None:
        raise RuntimeError("AuthPort not configured in app.state")
    return cast(AuthPort, auth_port)


auth_port_dep = Depends(get_auth_port)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = security_dep,
    auth_port: AuthPort = auth_port_dep,
) -> AuthContext:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ctx = auth_port.verify_token(credentials.credentials)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


current_user_dep = Depends(get_current_user)


def require_role(*allowed_roles: Role) -> Callable[..., Awaitable[AuthContext]]:
    async def _check(user: AuthContext = current_user_dep) -> AuthContext:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
