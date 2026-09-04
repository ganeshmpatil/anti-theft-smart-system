"""Authentication endpoints — register, login, profile, selfie upload, FCM token update."""

import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.database import User
from app.models.schemas import (
    FcmTokenUpdate, TokenResponse, UserLogin, UserProfileResponse, UserRegister,
)
from app.api.deps import (
    create_access_token, get_current_user, hash_password, verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")

    if body.email:
        existing_email = db.query(User).filter(User.email == body.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        phone=body.phone,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        address=body.address,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone number or password")

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/selfie")
def upload_selfie(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a selfie photo for the current user. Stored in MinIO under selfies/."""
    storage = getattr(request.app.state, "storage", None)
    if not storage:
        raise HTTPException(status_code=500, detail="Storage service not available")

    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are accepted")

    # Read file data
    image_data = file.file.read()
    if not image_data:
        raise HTTPException(status_code=400, detail="Empty file")

    # Determine extension from content type
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(file.content_type, "jpg")
    object_name = f"selfies/{user.id}.{ext}"

    success = storage.upload_image(object_name, image_data, content_type=file.content_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to upload selfie")

    user.selfie_path = object_name
    db.commit()

    return {"status": "ok", "selfie_path": object_name}


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Return the current user's profile."""
    selfie_url = ""
    if user.selfie_path:
        storage = getattr(request.app.state, "storage", None)
        if storage:
            selfie_url = storage.get_presigned_url(user.selfie_path)

    return UserProfileResponse(
        id=user.id,
        full_name=user.full_name,
        phone=user.phone,
        address=user.address,
        email=user.email,
        selfie_url=selfie_url,
    )


@router.post("/fcm-token")
def update_fcm_token(
    body: FcmTokenUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.fcm_token = body.fcm_token
    db.commit()
    return {"status": "ok"}
