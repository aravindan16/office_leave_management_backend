from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, users, leaves
from app.routers import activity_logs
from app.core.config import settings
from app.routers import holidays
from app.core.database import connect_to_mongo, close_mongo_connection

app = FastAPI(title="Office Leave Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("shutdown", close_mongo_connection)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(leaves.router, prefix="/api/leaves", tags=["leaves"])
app.include_router(activity_logs.router, prefix="/api/activity-logs", tags=["activity-logs"])
app.include_router(holidays.router, prefix="/api/holidays", tags=["holidays"])

@app.get("/")
async def root():
    return {"message": "Office Leave Management API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
