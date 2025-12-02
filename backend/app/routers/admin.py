from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_current_admin_user)]
)

# --- User Management ---
@router.get("/users", response_model=List[schemas.UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@router.put("/users/{user_id}/status", response_model=schemas.UserResponse)
async def update_user_status(user_id: str, is_approved: bool, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = is_approved
    db.commit()
    db.refresh(user)
    return user

@router.put("/users/{user_id}/role", response_model=schemas.UserResponse)
async def update_user_role(user_id: str, is_admin: bool, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_admin = is_admin
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

# --- RTD Config Management ---
@router.get("/rtd/configs", response_model=List[schemas.RTDConfigResponse])
async def read_rtd_configs(db: Session = Depends(database.get_db)):
    return db.query(models.RTDConfig).all()

@router.post("/rtd/configs", response_model=schemas.RTDConfigResponse)
async def create_rtd_config(config: schemas.RTDConfigCreate, db: Session = Depends(database.get_db)):
    db_config = models.RTDConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@router.delete("/rtd/configs/{line_name}")
async def delete_rtd_config(line_name: str, db: Session = Depends(database.get_db)):
    config = db.query(models.RTDConfig).filter(models.RTDConfig.line_name == line_name).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
    return {"message": "Config deleted"}

# --- ezDFS Config Management ---
@router.get("/ezdfs/configs", response_model=List[schemas.EzDFSConfigResponse])
async def read_ezdfs_configs(db: Session = Depends(database.get_db)):
    return db.query(models.EzDFSConfig).all()

@router.post("/ezdfs/configs", response_model=schemas.EzDFSConfigResponse)
async def create_ezdfs_config(config: schemas.EzDFSConfigCreate, db: Session = Depends(database.get_db)):
    db_config = models.EzDFSConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@router.delete("/ezdfs/configs/{module_name}")
async def delete_ezdfs_config(module_name: str, db: Session = Depends(database.get_db)):
    config = db.query(models.EzDFSConfig).filter(models.EzDFSConfig.module_name == module_name).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
    return {"message": "Config deleted"}
