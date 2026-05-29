from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal
from app.models import User
from app.routers import auth, avls, cms, incidents, scheduling
from app.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            with db.begin():
                seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="NCRTC Bus Management System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(avls.router, prefix="/api/avls", tags=["avls"])
app.include_router(scheduling.router, prefix="/api", tags=["scheduling"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(cms.router, prefix="/api/cms", tags=["cms"])


@app.get("/health")
def health():
    return {"status": "ok"}
