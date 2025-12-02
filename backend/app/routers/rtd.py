from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid
import asyncio
from datetime import datetime
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/api/rtd",
    tags=["rtd"],
    dependencies=[Depends(auth.get_current_active_user)]
)

# --- Step 1: Business Units ---
@router.get("/businesses", response_model=List[str])
async def get_businesses(db: Session = Depends(database.get_db)):
    results = db.query(models.RTDConfig.business_unit).distinct().all()
    return [r[0] for r in results]

# --- Step 2: Development Lines ---
@router.get("/lines", response_model=List[str])
async def get_lines(business_unit: str, db: Session = Depends(database.get_db)):
    results = db.query(models.RTDConfig.line_name).filter(models.RTDConfig.business_unit == business_unit).distinct().all()
    return [r[0] for r in results]

# --- Step 3: Rules ---
@router.get("/rules", response_model=List[str])
async def get_rules(line_name: str):
    return [f"Rule_A_{line_name}", f"Rule_B_{line_name}", "Common_Rule_X"]

# --- Step 4: Versions ---
@router.get("/rules/{rule_id}/versions")
async def get_rule_versions(rule_id: str):
    return {
        "old_version": "v1.0.0",
        "new_version": "v1.1.0 (Draft)"
    }

# --- Step 5: Target Lines ---
@router.get("/target-lines", response_model=List[str])
async def get_target_lines(business_unit: str, db: Session = Depends(database.get_db)):
    results = db.query(models.RTDConfig.line_name).filter(
        models.RTDConfig.business_unit == business_unit
    ).all()
    return [r[0] for r in results]

# --- Async Task Logic ---
async def run_rtd_test_task_wrapper(task_id: str):
    db_gen = database.get_db()
    bg_db = next(db_gen)
    try:
        task = bg_db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
        if task:
            task.status = "RUNNING"
            bg_db.commit()
        
        await asyncio.sleep(5) # Simulate work
        
        task.status = "SUCCESS"
        task.raw_result_path = f"/tmp/{task_id}_raw.zip"
        bg_db.commit()
    except Exception as e:
        print(f"Error: {e}")
        if task:
            task.status = "FAILED"
            bg_db.commit()
    finally:
        bg_db.close()

@router.post("/test/start")
async def start_rtd_test(
    target_lines: List[str],
    rule_id: str,
    background_tasks: BackgroundTasks,
    user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    task_id = str(uuid.uuid4())
    new_task = models.TestResults(
        task_id=task_id,
        user_id=user.user_id,
        test_type="RTD",
        status="PENDING",
        rtd_old_version="v1.0.0",
        rtd_new_version="v1.1.0"
    )
    db.add(new_task)
    db.commit()
    
    background_tasks.add_task(run_rtd_test_task_wrapper, task_id)
    return {"task_id": task_id, "status": "PENDING"}

@router.get("/test/status/{task_id}")
async def get_test_status(task_id: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task.task_id, "status": task.status, "progress": 100 if task.status == "SUCCESS" else 50}

@router.get("/test/{task_id}/result/raw")
async def download_raw_result(task_id: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task or task.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Result not ready")
    return {"file_path": task.raw_result_path, "message": "This would return a FileResponse"}

@router.post("/test/{task_id}/result/summary")
async def create_summary_result(task_id: str, summary_text: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.summary_result_path = f"/tmp/{task_id}_summary.pdf"
    db.commit()
    return {"message": "Summary created", "file_path": task.summary_result_path}
