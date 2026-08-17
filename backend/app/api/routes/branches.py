import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.routes.companies import get_owner_company
from app.db.session import get_db
from app.models.branch import Branch
from app.models.user import User
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate

router = APIRouter(prefix="/api/v1/branches", tags=["Branches"])


async def owner_company(db: AsyncSession, owner_id: int):
    company = await get_owner_company(db, owner_id)
    if company is None:
        raise HTTPException(status_code=409, detail="Complete company onboarding first")
    return company


def apply_branch(branch: Branch, payload: BranchCreate):
    for field, value in payload.model_dump().items():
        setattr(branch, field, value)


@router.post("", response_model=BranchResponse, status_code=201)
async def create_branch(payload: BranchCreate, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await owner_company(db, user.id)
    branch = Branch(company_id=company.id, branch_code=f"BR-{secrets.token_hex(3).upper()}", name=payload.name.strip())
    apply_branch(branch, payload); db.add(branch)
    try: await db.commit(); await db.refresh(branch)
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(status_code=409, detail="A branch with this name already exists") from exc
    return branch


@router.get("", response_model=list[BranchResponse])
async def list_branches(user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await owner_company(db, user.id)
    return list((await db.execute(select(Branch).where(Branch.company_id == company.id).order_by(Branch.created_at))).scalars().all())


@router.put("/{branch_id}", response_model=BranchResponse)
async def update_branch(branch_id: int, payload: BranchUpdate, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await owner_company(db, user.id); branch = await db.scalar(select(Branch).where(Branch.id == branch_id, Branch.company_id == company.id))
    if not branch: raise HTTPException(status_code=404, detail="Branch not found")
    apply_branch(branch, payload)
    try: await db.commit(); await db.refresh(branch)
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(status_code=409, detail="A branch with this name already exists") from exc
    return branch


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(branch_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await owner_company(db, user.id); branch = await db.scalar(select(Branch).where(Branch.id == branch_id, Branch.company_id == company.id))
    if not branch: raise HTTPException(status_code=404, detail="Branch not found")
    await db.delete(branch); await db.commit()
