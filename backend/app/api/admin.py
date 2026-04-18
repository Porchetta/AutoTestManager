from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.responses import success_response
from app.models.entities import EzdfsConfig, HostConfig, HostCredential, RtdConfig, User
from app.schemas.admin import (
    EzdfsConfigCreate,
    EzdfsConfigResponse,
    EzdfsConfigUpdate,
    HostConfigCreate,
    HostConfigResponse,
    HostCredentialCreate,
    HostCredentialResponse,
    HostCredentialUpdate,
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
    host.modifier = current_admin.user_name

    db.query(RtdConfig).filter(RtdConfig.host_name == name).update({"host_name": payload.name}, synchronize_session=False)
    db.query(EzdfsConfig).filter(EzdfsConfig.host_name == name).update({"host_name": payload.name}, synchronize_session=False)

    db.add(host)
    db.commit()
    db.refresh(host)
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

    if not host.credentials:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {
                    "code": "no_credential",
                    "message": "Host has no registered credential to probe SSH limit",
                },
            },
        )

    primary = host.credentials[0]
    item = HostSshLimitResponse(
        **probe_host_parallel_limit_info(host, primary.login_user)
    ).model_dump()
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


@router.get("/hosts/{name}/credentials")
def list_host_credentials(
    name: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    items = [HostCredentialResponse.model_validate(cred).model_dump() for cred in host.credentials]
    return success_response({"items": items})


@router.post("/hosts/{name}/credentials", status_code=status.HTTP_201_CREATED)
def create_host_credential(
    name: str,
    payload: HostCredentialCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    if not payload.login_user:
        raise HTTPException(status_code=400, detail="login_user is required")

    existing = (
        db.query(HostCredential)
        .filter(HostCredential.host_id == host.id, HostCredential.login_user == payload.login_user)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Credential already exists for this host")

    credential = HostCredential(
        host_id=host.id,
        login_user=payload.login_user,
        login_password=payload.login_password,
        modifier=current_admin.user_name,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return success_response({"credential": HostCredentialResponse.model_validate(credential).model_dump()})


@router.put("/hosts/{name}/credentials/{login_user}")
def update_host_credential(
    name: str,
    login_user: str,
    payload: HostCredentialUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    credential = (
        db.query(HostCredential)
        .filter(HostCredential.host_id == host.id, HostCredential.login_user == login_user)
        .first()
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    if payload.login_user != login_user:
        conflict = (
            db.query(HostCredential)
            .filter(
                HostCredential.host_id == host.id,
                HostCredential.login_user == payload.login_user,
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="Credential already exists for this host")

        db.query(RtdConfig).filter(
            RtdConfig.host_name == name,
            RtdConfig.login_user == login_user,
        ).update({"login_user": payload.login_user}, synchronize_session=False)
        db.query(EzdfsConfig).filter(
            EzdfsConfig.host_name == name,
            EzdfsConfig.login_user == login_user,
        ).update({"login_user": payload.login_user}, synchronize_session=False)

    credential.login_user = payload.login_user
    credential.login_password = payload.login_password
    credential.modifier = current_admin.user_name

    db.add(credential)
    db.commit()
    db.refresh(credential)
    return success_response({"credential": HostCredentialResponse.model_validate(credential).model_dump()})


@router.delete("/hosts/{name}/credentials/{login_user}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host_credential(
    name: str,
    login_user: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    host = db.query(HostConfig).filter(HostConfig.name == name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    credential = (
        db.query(HostCredential)
        .filter(HostCredential.host_id == host.id, HostCredential.login_user == login_user)
        .first()
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    referenced_rtd = db.query(RtdConfig).filter(
        RtdConfig.host_name == name, RtdConfig.login_user == login_user
    ).first()
    referenced_ezdfs = db.query(EzdfsConfig).filter(
        EzdfsConfig.host_name == name, EzdfsConfig.login_user == login_user
    ).first()
    if referenced_rtd or referenced_ezdfs:
        raise HTTPException(
            status_code=409, detail="Credential is referenced by another configuration"
        )

    db.delete(credential)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validate_host_credential(db: Session, host_name: str, login_user: str) -> None:
    host = db.query(HostConfig).filter(HostConfig.name == host_name).first()
    if host is None:
        raise HTTPException(status_code=404, detail="Referenced host not found")
    credential = (
        db.query(HostCredential)
        .filter(HostCredential.host_id == host.id, HostCredential.login_user == login_user)
        .first()
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Referenced host credential not found")


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

    _validate_host_credential(db, payload.host_name, payload.login_user)

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

    _validate_host_credential(db, payload.host_name, payload.login_user)

    config.line_name = payload.line_name
    config.line_id = payload.line_id
    config.business_unit = payload.business_unit
    config.home_dir_path = payload.home_dir_path
    config.host_name = payload.host_name
    config.login_user = payload.login_user
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

    _validate_host_credential(db, payload.host_name, payload.login_user)

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

    _validate_host_credential(db, payload.host_name, payload.login_user)

    config.module_name = payload.module_name
    config.port = payload.port
    config.home_dir_path = payload.home_dir_path
    config.host_name = payload.host_name
    config.login_user = payload.login_user
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
