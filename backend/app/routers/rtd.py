from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid
import asyncio
from datetime import datetime
from .. import database, models, schemas, auth

RTD_TASK_STATE = {}
RTD_SESSIONS = {}

router = APIRouter(
    prefix="/api/rtd",
    tags=["rtd"],
    dependencies=[Depends(auth.get_current_active_user)]
)

# --- Step 1: Business Units ---
@router.get("/businesses", response_model=List[str])
async def get_businesses(db: Session = Depends(database.get_db)):
    results = db.query(models.RTDConfig.business_unit).distinct().all()
    businesses = [r[0] for r in results]
    # Provide a minimal default list to keep UI usable when DB is empty
    return businesses or ["Memory", "Foundry", "NRD"]

# --- Step 2: Development Lines ---
@router.get("/lines", response_model=List[schemas.RTDLineResponse])
async def get_lines(business_unit: str, db: Session = Depends(database.get_db)):
    results = db.query(models.RTDConfig).filter(models.RTDConfig.business_unit == business_unit).all()
    return [
        schemas.RTDLineResponse(
            line_name=r.line_name,
            line_id=r.line_id,
            home_dir_path=r.home_dir_path
        )
        for r in results
    ]

# --- Step 3: Rules ---
@router.get("/rules", response_model=schemas.RTDRuleResponse)
async def get_rules(line_name: str, db: Session = Depends(database.get_db)):
    config = db.query(models.RTDConfig).filter(models.RTDConfig.line_name == line_name).first()
    if not config:
        raise HTTPException(status_code=404, detail="Line not found")

    # Mock rule discovery based on configured home_dir_path
    base = config.home_dir_path.rstrip("/").split("/")[-1]
    rules = [f"{base}_core", f"{base}_sanity", f"{base}_regression"]
    return schemas.RTDRuleResponse(home_dir_path=config.home_dir_path, rules=rules)

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
async def run_rtd_test_task_wrapper(task_id: str, line_names: List[str]):
    db_gen = database.get_db()
    bg_db = next(db_gen)
    try:
        task = bg_db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
        if task:
            task.status = "RUNNING"
            bg_db.commit()

        async def run_line(line_name: str):
            RTD_TASK_STATE[task_id]["lines"][line_name]["status"] = "RUNNING"
            RTD_TASK_STATE[task_id]["lines"][line_name]["progress"] = 30
            await asyncio.sleep(1)
            RTD_TASK_STATE[task_id]["lines"][line_name]["progress"] = 70
            await asyncio.sleep(1)
            RTD_TASK_STATE[task_id]["lines"][line_name]["status"] = "SUCCESS"
            RTD_TASK_STATE[task_id]["lines"][line_name]["progress"] = 100
            RTD_TASK_STATE[task_id]["lines"][line_name]["raw_result_path"] = f"/tmp/{task_id}_{line_name}_raw.zip"

        await asyncio.gather(*[run_line(line) for line in line_names])

        task.status = "SUCCESS"
        task.raw_result_path = f"/tmp/{task_id}_raw_bundle.zip"
        bg_db.commit()
    except Exception as e:
        print(f"Error: {e}")
        if task:
            task.status = "FAILED"
            bg_db.commit()
    finally:
        bg_db.close()

@router.post("/test/start", response_model=schemas.RTDStatusResponse)
async def start_rtd_test(
    payload: schemas.RTDTestRequest,
    background_tasks: BackgroundTasks,
    user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    active = db.query(models.TestResults).filter(
        models.TestResults.user_id == user.user_id,
        models.TestResults.test_type == "RTD",
        models.TestResults.status.in_(["RUNNING", "PENDING"])
    ).first()
    if active:
        raise HTTPException(status_code=400, detail="A RTD test is already running")

    task_id = str(uuid.uuid4())
    RTD_TASK_STATE[task_id] = {
        "lines": {ln: {"status": "PENDING", "raw_result_path": None, "progress": 0} for ln in payload.target_lines},
        "summary": None
    }

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

    background_tasks.add_task(run_rtd_test_task_wrapper, task_id, payload.target_lines)
    return await get_test_status(task_id, db)

@router.get("/test/status/{task_id}", response_model=schemas.RTDStatusResponse)
async def get_test_status(task_id: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    line_state = RTD_TASK_STATE.get(task_id, {}).get("lines", {})
    statuses = [
        schemas.RTDLineStatus(
            line_name=name,
            status=data.get("status", task.status),
            raw_result_path=data.get("raw_result_path"),
            progress=data.get("progress", 0)
        )
        for name, data in line_state.items()
    ]
    return schemas.RTDStatusResponse(
        task_id=task.task_id,
        status=task.status,
        line_statuses=statuses
    )

@router.get("/test/{task_id}/result/raw")
async def download_raw_result(task_id: str, line_name: str | None = None, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task or task.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Result not ready")
    state = RTD_TASK_STATE.get(task_id, {})
    if line_name:
        line_info = state.get("lines", {}).get(line_name)
        if not line_info:
            raise HTTPException(status_code=404, detail="Line not found")
        return {"file_path": line_info.get("raw_result_path")}
    return {"file_path": task.raw_result_path, "per_line": state.get("lines", {})}

@router.post("/test/{task_id}/result/summary")
async def create_summary_result(task_id: str, summary_text: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    line_state = RTD_TASK_STATE.get(task_id, {}).get("lines", {})
    if not line_state or any(item.get("status") != "SUCCESS" for item in line_state.values()):
        raise HTTPException(status_code=400, detail="All lines must finish before summary")

    task.summary_result_path = f"/tmp/{task_id}_summary.pdf"
    RTD_TASK_STATE[task_id]["summary"] = summary_text
    db.commit()
    return {"message": "Summary created", "file_path": task.summary_result_path}


@router.get("/session")
async def get_rtd_session(user: models.User = Depends(auth.get_current_active_user)):
    return RTD_SESSIONS.get(user.user_id, {})


@router.put("/session")
async def save_rtd_session(payload: schemas.RTDSessionPayload, user: models.User = Depends(auth.get_current_active_user)):
    RTD_SESSIONS[user.user_id] = payload.model_dump()
    return {"message": "Session saved"}


@router.delete("/session")
async def reset_rtd_session(user: models.User = Depends(auth.get_current_active_user)):
    RTD_SESSIONS.pop(user.user_id, None)
    return {"message": "Session cleared"}
