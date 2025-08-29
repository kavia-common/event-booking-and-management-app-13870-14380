from __future__ import annotations

import os
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, status


class Principal:
    """Represents the current caller principal and roles from API Gateway (placeholder)."""

    def __init__(self, user_id: Optional[str], roles: List[str]) -> None:
        self.user_id = user_id
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED", "false").lower() == "true"


# PUBLIC_INTERFACE
async def get_current_principal(
    x_user_id: Optional[str] = Header(default=None, alias="x-user-id"),
    x_user_roles: Optional[str] = Header(default=None, alias="x-user-roles"),
) -> Principal:
    """Resolve the principal from headers forwarded by API Gateway. Stubbed for local testing.

    In production: replace with OAuth2 bearer token validation or signed headers verification.
    """
    if _auth_disabled():
        # Local development: allow anonymous with admin+organizer roles via API keys (optional)
        roles = []
        return Principal(user_id="dev-user", roles=roles)

    roles: List[str] = []
    if x_user_roles:
        roles = [r.strip() for r in x_user_roles.split(",") if r.strip()]
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return Principal(user_id=x_user_id, roles=roles)


# PUBLIC_INTERFACE
def require_roles(*required: str):
    """Dependency factory to enforce roles (RBAC)."""

    async def _enforcer(principal: Principal = Depends(get_current_principal)) -> Principal:
        if _auth_disabled():
            return principal
        if not any(principal.has_role(r) for r in required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal

    return _enforcer
