from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid
import asyncio
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/api/ezdfs",
    tags=["ezdfs"],
    dependencies=[Depends(auth.get_current_active_user)]
)

# --- Step 1: Target Servers ---
@router.get("/servers", response_model=List[schemas.EzDFSConfigResponse])
async def get_servers(db: Session = Depends(database.get_db)):
    return db.query(models.EzDFSConfig).all()

# --- Step 2: Rules ---
@router.get("/rules", response_model=List[str])
async def get_rules(server_id: int):
    return [f"Rule_X_Server_{server_id}", f"Rule_Y_Server_{server_id}"]

# --- Favorites ---
@router.get("/favorites", response_model=List[str])
async def get_favorites(user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    return [f.rule_name for f in user.favorites]

@router.put("/favorites")
async def add_favorite(rule_name: str, target_server_id: int, user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    fav = models.UserFavorites(user_id=user.user_id, rule_name=rule_name, target_server_id=target_server_id)
    db.add(fav)
    db.commit()
    return {"message": "Favorite added"}

# --- Async Task Logic ---
async def run_ezdfs_test_task_wrapper(task_id: str):
    db_gen = database.get_db()
    bg_db = next(db_gen)
    try:
        task = bg_db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
        if task:
            task.status = "RUNNING"
            bg_db.commit()
        
        await asyncio.sleep(5) # Simulate work
        
        task.status = "SUCCESS"
        task.raw_result_path = f"/tmp/{task_id}_ezdfs_raw.zip"
        bg_db.commit()
    except Exception as e:
        if task:
            task.status = "FAILED"
            bg_db.commit()
    finally:
        bg_db.close()

@router.post("/test/start")
async def start_ezdfs_test(
    server_id: int,
    rule_name: str,
    background_tasks: BackgroundTasks,
    user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    task_id = str(uuid.uuid4())
    new_task = models.TestResults(
        task_id=task_id,
        user_id=user.user_id,
        test_type="EZDFS",
        status="PENDING"
    )
    db.add(new_task)
    db.commit()
    
    background_tasks.add_task(run_ezdfs_test_task_wrapper, task_id)
    return {"task_id": task_id, "status": "PENDING"}

@router.get("/test/status/{task_id}")
async def get_test_status(task_id: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task.task_id, "status": task.status}

@router.get("/test/{task_id}/result/raw")
async def download_raw_result(task_id: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task or task.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Result not ready")
    return {"file_path": task.raw_result_path}
