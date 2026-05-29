from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Notice, NoticeRead, User, UserRole
from app.schemas import NoticeCreate, NoticeDetailOut, NoticeOut, NoticeReadOut

router = APIRouter(dependencies=[Depends(get_current_user)])


def _notice_targets_user(notice: Notice, user: User) -> bool:
    audience = notice.audience_json or {}
    roles = audience.get("roles", [])
    if roles and user.role.value in roles:
        return True
    depot_ids = audience.get("depot_ids", [])
    if depot_ids and user.depot_id is not None and user.depot_id in depot_ids:
        return True
    depot_id = audience.get("depot_id")
    if depot_id is not None and user.depot_id == depot_id:
        return True
    return False


@router.post("/notices", response_model=NoticeOut, status_code=status.HTTP_201_CREATED)
def create_notice(
    body: NoticeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    publish_at = body.publish_at or datetime.now(timezone.utc)
    notice = Notice(
        title=body.title,
        body=body.body,
        audience_json=body.audience_json,
        publish_at=publish_at,
        created_by=current_user.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return NoticeOut.model_validate(notice)


@router.get("/notices", response_model=list[NoticeOut])
def list_notices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notices = db.query(Notice).order_by(Notice.publish_at.desc()).all()
    if current_user.role in (
        UserRole.admin,
        UserRole.depot_manager,
        UserRole.control_operator,
    ):
        return [NoticeOut.model_validate(n) for n in notices]
    return [NoticeOut.model_validate(n) for n in notices if _notice_targets_user(n, current_user)]


@router.get("/notices/{notice_id}", response_model=NoticeDetailOut)
def get_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    if current_user.role not in (UserRole.admin, UserRole.depot_manager):
        if not _notice_targets_user(notice, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Notice not visible")

    reads: list[NoticeReadOut] = []
    if current_user.role == UserRole.admin:
        read_rows = (
            db.query(NoticeRead, User)
            .join(User, NoticeRead.user_id == User.id)
            .filter(NoticeRead.notice_id == notice_id)
            .all()
        )
        for read, user in read_rows:
            reads.append(
                NoticeReadOut(
                    notice_id=read.notice_id,
                    user_id=read.user_id,
                    read_at=read.read_at,
                    username=user.username,
                    full_name=user.full_name,
                )
            )

    return NoticeDetailOut(
        **NoticeOut.model_validate(notice).model_dump(),
        reads=reads,
    )


@router.post("/notices/{notice_id}/read", response_model=NoticeReadOut)
def mark_notice_read(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    if current_user.role not in (UserRole.admin, UserRole.depot_manager):
        if not _notice_targets_user(notice, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Notice not visible")

    existing = (
        db.query(NoticeRead)
        .filter(NoticeRead.notice_id == notice_id, NoticeRead.user_id == current_user.id)
        .first()
    )
    if existing:
        return NoticeReadOut(
            notice_id=existing.notice_id,
            user_id=existing.user_id,
            read_at=existing.read_at,
            username=current_user.username,
            full_name=current_user.full_name,
        )

    now = datetime.now(timezone.utc)
    read = NoticeRead(notice_id=notice_id, user_id=current_user.id, read_at=now)
    db.add(read)
    db.commit()
    return NoticeReadOut(
        notice_id=read.notice_id,
        user_id=read.user_id,
        read_at=read.read_at,
        username=current_user.username,
        full_name=current_user.full_name,
    )
