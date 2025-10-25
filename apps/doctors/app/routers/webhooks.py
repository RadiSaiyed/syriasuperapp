from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, AnyHttpUrl, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import WebhookEndpoint
from ..utils.webhooks import send_webhooks


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookEndpointCreateIn(BaseModel):
    url: AnyHttpUrl
    secret: str = Field(..., min_length=6, max_length=128)


class WebhookEndpointOut(BaseModel):
    id: str
    url: str
    created_at: str


@router.get("/endpoints", response_model=list[WebhookEndpointOut])
def list_endpoints(db: Session = Depends(get_db)):
    eps = db.query(WebhookEndpoint).order_by(WebhookEndpoint.created_at.desc()).all()
    return [WebhookEndpointOut(id=str(e.id), url=e.url, created_at=e.created_at.isoformat()) for e in eps]


@router.post("/endpoints", response_model=WebhookEndpointOut)
def create_endpoint(payload: WebhookEndpointCreateIn, db: Session = Depends(get_db)):
    existing = db.query(WebhookEndpoint).filter(WebhookEndpoint.url == str(payload.url)).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Endpoint already exists")
    ep = WebhookEndpoint(url=str(payload.url), secret=payload.secret)
    db.add(ep)
    db.flush()
    return WebhookEndpointOut(id=str(ep.id), url=ep.url, created_at=ep.created_at.isoformat())


@router.delete("/endpoints/{endpoint_id}")
def delete_endpoint(endpoint_id: str, db: Session = Depends(get_db)):
    ep = db.get(WebhookEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(ep)
    return {"detail": "ok"}


@router.post("/test")
def test_webhooks(tasks: BackgroundTasks, db: Session = Depends(get_db)):
    send_webhooks(db, "webhook.test", {"hello": "world"}, tasks=tasks)
    return {"detail": "queued"}

