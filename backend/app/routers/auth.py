from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)

@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_approved:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not approved by admin",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.user_id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.put("/password", response_model=schemas.UserResponse)
async def change_password(
    password_data: schemas.PasswordChange,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    if not auth.verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    current_user.password_hash = auth.get_password_hash(password_data.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/register", response_model=schemas.UserResponse)
async def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.user_id == user.user_id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    # Default: not admin, not approved (unless it's the very first user? No, let's stick to spec: admin approves)
    # For testing convenience, if user_id is 'admin', make it admin/approved? No, init.sql handles that.
    new_user = models.User(
        user_id=user.user_id,
        password_hash=hashed_password,
        is_admin=False,
        is_approved=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
