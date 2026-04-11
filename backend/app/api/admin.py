from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.responses import success_response
from app.models.entities import EzdfsConfig, HostConfig, RtdConfig, User
from app.schemas.admin import (
    EzdfsConfigCreate,
    EzdfsConfigResponse,
    EzdfsConfigUpdate,
    HostConfigCreate,
    HostConfigResponse,
    HostSshLimitResponse,
    HostConfigUpdate,
    RoleUpdateRequest,
    UserUpdateRequest,
    RtdConfigCreate,
    RtdConfigResponse,
    RtdConfigUpdate,
    UserResponse,
)
from app.services.ssh_runtime import get_host_parallel_limit_info, probe_host_parallel_limit_info

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
def list_users(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return success_response({"items": [UserResponse.model_validate(user).model_dump() for user in users]})


@router.put("/users/{user_id}/approve")
def approve_user(
    user_id: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response({"user": UserResponse.model_validate(user).model_dump()})


@router.put("/users/{user_id}/reject")
def reject_user(
    user_id: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = False
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response({"user": UserResponse.model_validate(user).model_dump()})


@router.put("/users/{user_id}/role")
def update_role(
    user_id: str,
    payload: RoleUpdateRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_admin = payload.is_admin
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response({"user": UserResponse.model_validate(user).model_dump()})


@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.module_name = payload.module_name
    user.is_admin = payload.is_admin
    user.is_approved = payload.is_approved
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response({"user": UserResponse.model_validate(user).model_dump()})


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/hosts")
def list_hosts(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(HostConfig).order_by(HostConfig.created_at.desc()).all()
    return success_response({"items": [HostConfigResponse.model_validate(item).model_dump() for item in items]})


@router.get("/hosts/ssh-limits")
def list_host_ssh_limits(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(HostConfig).order_by(HostConfig.name.asc()).all()
    response_items = [HostSshLimitResponse(**get_host_parallel_limit_info(item)).model_dump() for item in items]
    return success_response({"items": response_items})


@router.post("/hosts", status_code=status.HTTP_201_CREATED)
def create_host(
    payload: HostConfigCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(HostConfig).filter(HostConfig.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Host already exists")

    host = HostConfig(**payload.model_dump(), modifier=current_admin.user_name)
    db.add(host)
    db.commit()
    db.refresh(host)
    probe_host_parallel_limit_info(host)
    return success_response({"host": HostConfigResponse.model_validate(host).model_dump()})


@router.put("/hosts/{name}")
def update_host(
    name: str,
    payload: HostConfigUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    if payload.name != name and db.query(HostConfig).filter(HostConfig.name == payload.name).first():
        raise HTTPException(status_code=409, detail="Host already exists")

    host.name = payload.name
    host.ip = payload.ip
    host.login_user = payload.login_user
    host.login_password = payload.login_password
    host.modifier = current_admin.user_name

    db.query(RtdConfig).filter(RtdConfig.host_name == name).update({"host_name": payload.name}, synchronize_session=False)
    db.query(EzdfsConfig).filter(EzdfsConfig.host_name == name).update({"host_name": payload.name}, synchronize_session=False)

    db.add(host)
    db.commit()
    db.refresh(host)
    probe_host_parallel_limit_info(host)
    return success_response({"host": HostConfigResponse.model_validate(host).model_dump()})


@router.post("/hosts/{name}/ssh-limits/probe")
def probe_host_ssh_limit(
    name: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    item = HostSshLimitResponse(**probe_host_parallel_limit_info(host)).model_dump()
    return success_response({"item": item})


@router.delete("/hosts/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(
    name: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    is_referenced = db.query(RtdConfig).filter(RtdConfig.host_name == name).first() or db.query(EzdfsConfig).filter(EzdfsConfig.host_name == name).first()
    if is_referenced:
        raise HTTPException(status_code=409, detail="Host is referenced by another configuration")

    db.delete(host)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/rtd/configs")
def list_rtd_configs(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(RtdConfig).order_by(RtdConfig.created_at.desc()).all()
    return success_response({"items": [RtdConfigResponse.model_validate(item).model_dump() for item in items]})


@router.post("/rtd/configs", status_code=status.HTTP_201_CREATED)
def create_rtd_config(
    payload: RtdConfigCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(RtdConfig).filter(RtdConfig.line_name == payload.line_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="RTD config already exists")

    if db.query(HostConfig).filter(HostConfig.name == payload.host_name).first() is None:
        raise HTTPException(status_code=404, detail="Referenced host not found")

    config = RtdConfig(**payload.model_dump(), modifier=current_admin.user_name)
    db.add(config)
    db.commit()
    db.refresh(config)
    return success_response({"config": RtdConfigResponse.model_validate(config).model_dump()})


@router.put("/rtd/configs/{line_name}")
def update_rtd_config(
    line_name: str,
    payload: RtdConfigUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise HTTPException(status_code=404, detail="RTD config not found")

    if payload.line_name != line_name and db.query(RtdConfig).filter(RtdConfig.line_name == payload.line_name).first():
        raise HTTPException(status_code=409, detail="RTD config already exists")

    if db.query(HostConfig).filter(HostConfig.name == payload.host_name).first() is None:
        raise HTTPException(status_code=404, detail="Referenced host not found")

    config.line_name = payload.line_name
    config.line_id = payload.line_id
    config.business_unit = payload.business_unit
    config.home_dir_path = payload.home_dir_path
    config.host_name = payload.host_name
    config.modifier = current_admin.user_name
    db.add(config)
    db.commit()
    db.refresh(config)
    return success_response({"config": RtdConfigResponse.model_validate(config).model_dump()})


@router.delete("/rtd/configs/{line_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rtd_config(
    line_name: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise HTTPException(status_code=404, detail="RTD config not found")
    db.delete(config)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ezdfs/configs")
def list_ezdfs_configs(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(EzdfsConfig).order_by(EzdfsConfig.created_at.desc()).all()
    return success_response({"items": [EzdfsConfigResponse.model_validate(item).model_dump() for item in items]})


@router.post("/ezdfs/configs", status_code=status.HTTP_201_CREATED)
def create_ezdfs_config(
    payload: EzdfsConfigCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == payload.module_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="ezDFS config already exists")

    if db.query(HostConfig).filter(HostConfig.name == payload.host_name).first() is None:
        raise HTTPException(status_code=404, detail="Referenced host not found")

    config = EzdfsConfig(**payload.model_dump(), modifier=current_admin.user_name)
    db.add(config)
    db.commit()
    db.refresh(config)
    return success_response({"config": EzdfsConfigResponse.model_validate(config).model_dump()})


@router.put("/ezdfs/configs/{module_name}")
def update_ezdfs_config(
    module_name: str,
    payload: EzdfsConfigUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise HTTPException(status_code=404, detail="ezDFS config not found")

    if payload.module_name != module_name and db.query(EzdfsConfig).filter(EzdfsConfig.module_name == payload.module_name).first():
        raise HTTPException(status_code=409, detail="ezDFS config already exists")

    if db.query(HostConfig).filter(HostConfig.name == payload.host_name).first() is None:
        raise HTTPException(status_code=404, detail="Referenced host not found")

    config.module_name = payload.module_name
    config.port = payload.port
    config.home_dir_path = payload.home_dir_path
    config.host_name = payload.host_name
    config.modifier = current_admin.user_name
    db.add(config)
    db.commit()
    db.refresh(config)
    return success_response({"config": EzdfsConfigResponse.model_validate(config).model_dump()})


@router.delete("/ezdfs/configs/{module_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ezdfs_config(
    module_name: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise HTTPException(status_code=404, detail="ezDFS config not found")
    db.delete(config)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
