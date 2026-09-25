"""Registration, login and session endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.v1.dependencies import get_auth_service, get_current_user
from app.api.v1.schemas import Credentials
from app.domain.account_ports import AccountIdentity
from app.domain.company_colors import COMPANY_COLORS
from app.services.auth import SESSION_COOKIE, SESSION_LIFETIME, AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


def check_attempt(request: Request, auth: AuthService) -> None:
    """Throttle by socket peer; never trust arbitrary forwarding headers."""
    peer = request.client.host if request.client else "unknown"
    if not auth.accounts.allow_attempt(peer):
        raise HTTPException(429, "Zu viele Versuche. Bitte später versuchen.")


def set_session(
    request: Request,
    response: Response,
    auth: AuthService,
    user: AccountIdentity,
) -> dict:
    """Rotate the browser session and set a protected cookie."""
    old_token = request.cookies.get(SESSION_COOKIE, "")
    token = auth.issue_session(user["id"])
    auth.accounts.revoke_session(old_token)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_LIFETIME,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return dict(user)


@router.post("/register", status_code=201)
def register(
    body: Credentials,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    """Create an account and sign in immediately."""
    check_attempt(request, auth)
    try:
        user = auth.register(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return set_session(request, response, auth, user)


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    """Authenticate credentials and rotate the session token."""
    check_attempt(request, auth)
    try:
        user = auth.authenticate(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    return set_session(request, response, auth, user)


@router.get("/me")
def current_user(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    """Return the authenticated player's public identity."""
    return {
        **user,
        "company_color": request.app.state.preferences.read(
            user["id"]
        ).company_color,
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    """Revoke the current session and remove the browser cookie."""
    auth.accounts.revoke_session(request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


class ColorPreference(BaseModel):
    """HTTP input for one curated cosmetic selection."""

    company_color: str


@router.get("/preferences")
def preferences(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    """Project the authenticated preference and supported palette."""
    return {
        "company_color": request.app.state.preferences.read(
            user["id"]
        ).company_color,
        "palette": COMPANY_COLORS,
    }


@router.put("/preferences")
def update_preferences(
    body: ColorPreference,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    """Translate a validated account cosmetic change to HTTP."""
    try:
        result = request.app.state.preferences.update(
            user["id"], body.company_color
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"company_color": result.company_color}
