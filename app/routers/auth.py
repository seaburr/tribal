import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, hash_password, verify_password
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = "session"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=_COOKIE_MAX_AGE,
    )


@router.post("/register", response_model=schemas.UserResponse, status_code=201)
def register(req: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    email = req.email.lower().strip()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    is_first_user = db.query(models.User).count() == 0
    user = models.User(
        email=email,
        display_name=req.display_name.strip() if req.display_name else None,
        hashed_password=hash_password(req.password),
        is_admin=is_first_user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    response = JSONResponse(
        status_code=201,
        content={"id": user.id, "email": user.email, "display_name": user.display_name},
    )
    _set_auth_cookie(response, token)
    return response


@router.post("/login", response_model=schemas.UserResponse)
async def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        await asyncio.sleep(1)  # slow brute-force
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_access_token(user.id)
    response = JSONResponse(
        content={"id": user.id, "email": user.email, "display_name": user.display_name}
    )
    _set_auth_cookie(response, token)
    return response


@router.post("/logout")
def logout():
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(_COOKIE)
    return response


@router.get("/me", response_model=schemas.UserResponse)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
