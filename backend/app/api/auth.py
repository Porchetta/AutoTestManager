from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.entities import User
from app.schemas.auth import LoginRequest, PasswordChangeRequest, SignupRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.user_id == payload.user_id).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {
                    "code": "USER_ALREADY_EXISTS",
                    "message": "이미 존재하는 사용자 ID입니다.",
                    "detail": {"user_id": payload.user_id},
                },
            },
        )

    user = User(
        user_id=payload.user_id,
        password_hash=get_password_hash(payload.password),
        user_name=payload.user_name,
        module_name=payload.module_name,
        is_admin=False,
        is_approved=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return success_response(
        {
            "user": UserResponse.model_validate(user).model_dump(),
            "message": "회원가입이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다.",
        }
    )


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "아이디 또는 비밀번호가 올바르지 않습니다.",
                    "detail": {},
                },
            },
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {
                    "code": "USER_NOT_APPROVED",
                    "message": "승인되지 않은 계정입니다.",
                    "detail": {},
                },
            },
        )

    access_token = create_access_token(subject=user.user_id)
    return success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
        }
    )


@router.post("/logout")
def logout():
    return success_response({"message": "로그아웃 처리되었습니다."})


@router.put("/password")
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "PASSWORD_MISMATCH",
                    "message": "현재 비밀번호가 일치하지 않습니다.",
                    "detail": {},
                },
            },
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return success_response({"message": "비밀번호가 변경되었습니다."})


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success_response({"user": UserResponse.model_validate(current_user).model_dump()})

