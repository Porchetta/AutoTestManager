from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/api/mypage",
    tags=["mypage"],
    dependencies=[Depends(auth.get_current_active_user)]
)

@router.get("/rtd/last-result")
async def get_last_rtd_result(user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    result = db.query(models.TestResults).filter(
        models.TestResults.user_id == user.user_id,
        models.TestResults.test_type == "RTD"
    ).order_by(desc(models.TestResults.request_time)).first()
    
    if not result:
        return {"message": "No recent RTD tests"}
    return result

@router.get("/ezdfs/last-result")
async def get_last_ezdfs_result(user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    result = db.query(models.TestResults).filter(
        models.TestResults.user_id == user.user_id,
        models.TestResults.test_type == "EZDFS"
    ).order_by(desc(models.TestResults.request_time)).first()
    
    if not result:
        return {"message": "No recent ezDFS tests"}
    return result
