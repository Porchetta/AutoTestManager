from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid
import asyncio
from .. import database, models, schemas, auth

EZDFS_TASK_STATE = {}
EZDFS_SESSIONS = {}

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
async def get_rules(module_name: str, db: Session = Depends(database.get_db)):
    config = db.query(models.EzDFSConfig).filter(models.EzDFSConfig.module_name == module_name).first()
    if not config:
        raise HTTPException(status_code=404, detail="Target server not found")

    base = config.home_dir_path.rstrip("/").split("/")[-1]
    return [f"{base}_full", f"{base}_smoke", f"{base}_nightly"]

# --- Favorites ---
@router.get("/favorites", response_model=List[str])
async def get_favorites(user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    return [f.rule_name for f in user.ezdfs_favorites]

@router.put("/favorites")
async def add_favorite(rule_name: str, module_name: str, user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    fav = models.UserEZFDSFavorite(user_id=user.user_id, rule_name=rule_name, module_name=module_name)
    db.add(fav)
    db.commit()
    return {"message": "Favorite added"}

# --- Async Task Logic ---
async def run_ezdfs_test_task_wrapper(task_id: str, targets: List[schemas.EzdfsTarget]):
    db_gen = database.get_db()
    bg_db = next(db_gen)
    try:
        task = bg_db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
        if task:
            task.status = "RUNNING"
            bg_db.commit()

        async def run_target(target: schemas.EzdfsTarget):
            EZDFS_TASK_STATE[task_id]["targets"][target.module_name]["status"] = "RUNNING"
            EZDFS_TASK_STATE[task_id]["targets"][target.module_name]["progress"] = 40
            await asyncio.sleep(1)
            EZDFS_TASK_STATE[task_id]["targets"][target.module_name]["progress"] = 80
            await asyncio.sleep(1)
            EZDFS_TASK_STATE[task_id]["targets"][target.module_name]["status"] = "SUCCESS"
            EZDFS_TASK_STATE[task_id]["targets"][target.module_name]["progress"] = 100
            EZDFS_TASK_STATE[task_id]["targets"][target.module_name]["raw_result_path"] = f"/tmp/{task_id}_{target.module_name}_raw.zip"

        await asyncio.gather(*[run_target(t) for t in targets])

        task.status = "SUCCESS"
        task.raw_result_path = f"/tmp/{task_id}_ezdfs_bundle.zip"
        bg_db.commit()
    except Exception as e:
        if task:
            task.status = "FAILED"
            bg_db.commit()
    finally:
        bg_db.close()

@router.post("/test/start", response_model=schemas.EzdfsStatusResponse)
async def start_ezdfs_test(
    payload: schemas.EzdfsTestRequest,
    background_tasks: BackgroundTasks,
    user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    active = db.query(models.TestResults).filter(
        models.TestResults.user_id == user.user_id,
        models.TestResults.test_type == "EZDFS",
        models.TestResults.status.in_(["RUNNING", "PENDING"])
    ).first()
    if active:
        raise HTTPException(status_code=400, detail="An ezDFS test is already running")

    task_id = str(uuid.uuid4())
    EZDFS_TASK_STATE[task_id] = {
        "targets": {t.module_name: {"status": "PENDING", "raw_result_path": None, "progress": 0} for t in payload.targets},
        "summary": None
    }

    new_task = models.TestResults(
        task_id=task_id,
        user_id=user.user_id,
        test_type="EZDFS",
        status="PENDING"
    )
    db.add(new_task)
    db.commit()

    background_tasks.add_task(run_ezdfs_test_task_wrapper, task_id, payload.targets)
    return await get_test_status(task_id, db)

@router.get("/test/status/{task_id}", response_model=schemas.EzdfsStatusResponse)
async def get_test_status(task_id: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    target_state = EZDFS_TASK_STATE.get(task_id, {}).get("targets", {})
    statuses = [
        schemas.EzdfsTargetStatus(
            module_name=name,
            status=data.get("status", task.status),
            raw_result_path=data.get("raw_result_path"),
            progress=data.get("progress", 0)
        )
        for name, data in target_state.items()
    ]
    return schemas.EzdfsStatusResponse(task_id=task.task_id, status=task.status, target_statuses=statuses)

@router.get("/test/{task_id}/result/raw")
async def download_raw_result(task_id: str, module_name: str | None = None, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task or task.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Result not ready")
    state = EZDFS_TASK_STATE.get(task_id, {})
    if module_name:
        module_state = state.get("targets", {}).get(module_name)
        if not module_state:
            raise HTTPException(status_code=404, detail="Module not found")
        return {"file_path": module_state.get("raw_result_path")}
    return {"file_path": task.raw_result_path, "per_target": state.get("targets", {})}


@router.post("/test/{task_id}/result/summary")
async def create_summary_result(task_id: str, summary_text: str, db: Session = Depends(database.get_db)):
    task = db.query(models.TestResults).filter(models.TestResults.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    target_state = EZDFS_TASK_STATE.get(task_id, {}).get("targets", {})
    if not target_state or any(item.get("status") != "SUCCESS" for item in target_state.values()):
        raise HTTPException(status_code=400, detail="All targets must finish before summary")

    task.summary_result_path = f"/tmp/{task_id}_ezdfs_summary.pdf"
    EZDFS_TASK_STATE[task_id]["summary"] = summary_text
    db.commit()
    return {"message": "Summary created", "file_path": task.summary_result_path}


@router.get("/session")
async def get_ezdfs_session(user: models.User = Depends(auth.get_current_active_user)):
    return EZDFS_SESSIONS.get(user.user_id, {})


@router.put("/session")
async def save_ezdfs_session(payload: schemas.EzdfsSessionPayload, user: models.User = Depends(auth.get_current_active_user)):
    EZDFS_SESSIONS[user.user_id] = payload.model_dump()
    return {"message": "Session saved"}


@router.delete("/session")
async def reset_ezdfs_session(user: models.User = Depends(auth.get_current_active_user)):
    EZDFS_SESSIONS.pop(user.user_id, None)
    return {"message": "Session cleared"}
