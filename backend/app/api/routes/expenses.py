from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_company_access
from app.db.session import get_db
from app.models.branch import Branch
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import EXPENSE_CATEGORIES, ExpenseCreate, ExpenseListResponse, ExpenseResponse, ExpenseUpdate
from app.services.audit import add_audit

router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])


def expense_data(expense: Expense, branch_name: str | None, creator: str | None) -> dict:
    return {
        "id": expense.id, "expense_date": expense.expense_date, "category": expense.category,
        "amount": expense.amount, "branch_id": expense.branch_id, "branch_name": branch_name,
        "payee": expense.payee, "payment_mode": expense.payment_mode,
        "reference_number": expense.reference_number, "description": expense.description,
        "notes": expense.notes, "created_by": creator, "created_at": expense.created_at,
        "updated_at": expense.updated_at,
    }


async def validate_branch(db: AsyncSession, company_id: int, branch_id: int | None, scoped_branch_id: int | None) -> int | None:
    if scoped_branch_id is not None:
        if branch_id is not None and branch_id != scoped_branch_id:
            raise HTTPException(status_code=403, detail="Expense is outside your branch scope")
        return scoped_branch_id
    if branch_id is not None and not await db.scalar(select(Branch.id).where(Branch.id == branch_id, Branch.company_id == company_id)):
        raise HTTPException(status_code=400, detail="Invalid branch")
    return branch_id


@router.get("/categories")
async def categories(access=Depends(get_company_access("expenses.view"))):
    return [{"value": value, "label": value.replace("_", " ").title()} for value in EXPENSE_CATEGORIES]


@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None), payment_mode: str | None = Query(default=None),
    date_from: date | None = None, date_to: date | None = None,
    access=Depends(get_company_access("expenses.view")), db: AsyncSession = Depends(get_db),
):
    company, _, branch_id = access
    filters = [Expense.company_id == company.id]
    if branch_id is not None: filters.append(Expense.branch_id == branch_id)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Expense.description.ilike(term), Expense.payee.ilike(term), Expense.reference_number.ilike(term), Expense.notes.ilike(term)))
    if category: filters.append(Expense.category == category)
    if payment_mode: filters.append(Expense.payment_mode == payment_mode)
    if date_from: filters.append(Expense.expense_date >= date_from)
    if date_to: filters.append(Expense.expense_date <= date_to)
    rows = (await db.execute(
        select(Expense, Branch.name, User.email).outerjoin(Branch, Expense.branch_id == Branch.id).outerjoin(User, Expense.created_by_user_id == User.id)
        .where(*filters).order_by(Expense.expense_date.desc(), Expense.id.desc())
    )).all()
    totals = (await db.execute(select(Expense.category, func.sum(Expense.amount)).where(*filters).group_by(Expense.category))).all()
    items = [expense_data(expense, branch_name, creator) for expense, branch_name, creator in rows]
    return {"items": items, "total_amount": sum((expense.amount for expense, _, _ in rows), start=0), "count": len(items), "category_totals": dict(totals)}


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate, request: Request, access=Depends(get_company_access("expenses.manage")), db: AsyncSession = Depends(get_db)):
    company, user, scoped_branch_id = access
    branch_id = await validate_branch(db, company.id, payload.branch_id, scoped_branch_id)
    expense = Expense(company_id=company.id, created_by_user_id=user.id, branch_id=branch_id, **payload.model_dump(exclude={"branch_id"}))
    db.add(expense); await db.flush()
    add_audit(db, company_id=company.id, user_id=user.id, action="create", entity_type="expense", entity_id=expense.id, description=f"Recorded {payload.category.replace('_', ' ')} expense", request=request, new_values={"amount": str(payload.amount), "category": payload.category})
    await db.commit(); await db.refresh(expense)
    branch_name = await db.scalar(select(Branch.name).where(Branch.id == expense.branch_id)) if expense.branch_id else None
    return expense_data(expense, branch_name, user.email)


async def owned_expense(db: AsyncSession, expense_id: int, company_id: int, branch_id: int | None) -> Expense:
    filters = [Expense.id == expense_id, Expense.company_id == company_id]
    if branch_id is not None: filters.append(Expense.branch_id == branch_id)
    expense = await db.scalar(select(Expense).where(*filters))
    if not expense: raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: int, payload: ExpenseUpdate, request: Request, access=Depends(get_company_access("expenses.manage")), db: AsyncSession = Depends(get_db)):
    company, user, scoped_branch_id = access
    expense = await owned_expense(db, expense_id, company.id, scoped_branch_id)
    branch_id = await validate_branch(db, company.id, payload.branch_id, scoped_branch_id)
    old_values = {"amount": str(expense.amount), "category": expense.category}
    for field, value in payload.model_dump(exclude={"branch_id"}).items(): setattr(expense, field, value)
    expense.branch_id = branch_id
    add_audit(db, company_id=company.id, user_id=user.id, action="update", entity_type="expense", entity_id=expense.id, description="Updated expense", request=request, old_values=old_values, new_values={"amount": str(payload.amount), "category": payload.category})
    await db.commit(); await db.refresh(expense)
    branch_name = await db.scalar(select(Branch.name).where(Branch.id == expense.branch_id)) if expense.branch_id else None
    return expense_data(expense, branch_name, user.email)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: int, request: Request, access=Depends(get_company_access("expenses.manage")), db: AsyncSession = Depends(get_db)):
    company, user, scoped_branch_id = access
    expense = await owned_expense(db, expense_id, company.id, scoped_branch_id)
    add_audit(db, company_id=company.id, user_id=user.id, action="delete", entity_type="expense", entity_id=expense.id, description="Deleted expense", request=request, old_values={"amount": str(expense.amount), "category": expense.category})
    await db.delete(expense); await db.commit()
