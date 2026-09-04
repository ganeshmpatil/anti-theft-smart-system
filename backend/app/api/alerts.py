"""Alert history and management endpoints."""

import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.database import Alert, Device, Farm, User
from app.models.schemas import AlertAcknowledge, AlertResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _get_storage(request: Request):
    return getattr(request.app.state, "storage", None)


def _user_device_ids(user: User, db: Session) -> list[int]:
    """Get all device IDs owned by the user."""
    farm_ids = [f.id for f in db.query(Farm).filter(Farm.owner_id == user.id).all()]
    if not farm_ids:
        return []
    return [d.id for d in db.query(Device).filter(Device.farm_id.in_(farm_ids)).all()]


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    device_id: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_ids = _user_device_ids(user, db)
    if not allowed_ids:
        return []

    query = db.query(Alert).filter(Alert.device_id.in_(allowed_ids))

    if device_id is not None:
        if device_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Access denied")
        query = query.filter(Alert.device_id == device_id)

    if from_date:
        query = query.filter(Alert.created_at >= from_date)
    if to_date:
        query = query.filter(Alert.created_at <= to_date)

    return query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    allowed_ids = _user_device_ids(user, db)
    if alert.device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    return alert


@router.get("/{alert_id}/image")
def get_alert_image(
    alert_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    allowed_ids = _user_device_ids(user, db)
    if alert.device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    if not alert.image_path:
        raise HTTPException(status_code=404, detail="No image available")

    storage = _get_storage(request)
    if not storage:
        raise HTTPException(status_code=500, detail="Storage service not available")

    try:
        response = storage._client.get_object(storage._bucket, alert.image_path)
        return StreamingResponse(
            io.BytesIO(response.read()),
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found in storage")
    finally:
        try:
            response.close()
            response.release_conn()
        except Exception:
            pass


@router.patch("/{alert_id}/ack", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledge,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    allowed_ids = _user_device_ids(user, db)
    if alert.device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    alert.acknowledged = body.acknowledged
    db.commit()
    db.refresh(alert)
    return alert
