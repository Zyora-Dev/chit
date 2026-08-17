from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.advances import router as advances_router
from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.audit import router as audit_router
from app.api.routes.branches import router as branches_router
from app.api.routes.chits import router as chits_router
from app.api.routes.companies import router as companies_router
from app.api.routes.communications import router as communications_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.employees import router as employees_router
from app.api.routes.health import router as health_router
from app.api.routes.members import router as members_router
from app.api.routes.payroll import router as payroll_router
from app.api.routes.users import router as users_router
from app.core.config import settings

app = FastAPI(
    title="zChit API",
    description="Backend API for the zChit fund management platform.",
    version="0.1.0",
)

app.include_router(advances_router)
app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(branches_router)
app.include_router(chits_router)
app.include_router(companies_router)
app.include_router(communications_router)
app.include_router(dashboard_router)
app.include_router(employees_router)
app.include_router(health_router)
app.include_router(members_router)
app.include_router(payroll_router)
app.include_router(users_router)

upload_directory = Path(settings.upload_directory)
upload_directory.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_directory), name="uploads")


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {"message": "Welcome to the zChit API"}
