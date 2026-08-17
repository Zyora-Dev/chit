import secrets
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.chit import LedgerEntry


def document_number(prefix: str, company_code: str, value_date: date) -> str:
    return f"{company_code}-{prefix}-{value_date:%Y%m%d}-{secrets.token_hex(3).upper()}"


async def validate_branch(db: AsyncSession, company_id: int, branch_id: int | None) -> None:
    if branch_id is None:
        return
    branch = await db.scalar(
        select(Branch).where(Branch.id == branch_id, Branch.company_id == company_id, Branch.is_active.is_(True))
    )
    if branch is None:
        raise ValueError("Selected branch is invalid or inactive")


def post_entries(
    db: AsyncSession,
    *,
    company_id: int,
    branch_id: int | None,
    group_id: int,
    member_id: int,
    source_type: str,
    source_id: int,
    entry_date: date,
    reference_number: str,
    posted_by_user_id: int,
    entries: list[tuple[str, str, Decimal, str]],
) -> None:
    debits = sum((amount for entry_type, _, amount, _ in entries if entry_type == "debit"), Decimal("0"))
    credits = sum((amount for entry_type, _, amount, _ in entries if entry_type == "credit"), Decimal("0"))
    if debits != credits:
        raise ValueError("Ledger entries are not balanced")
    for entry_type, account_code, amount, description in entries:
        db.add(
            LedgerEntry(
                company_id=company_id,
                branch_id=branch_id,
                group_id=group_id,
                member_id=member_id,
                source_type=source_type,
                source_id=source_id,
                entry_type=entry_type,
                account_code=account_code,
                amount=amount,
                entry_date=entry_date,
                description=description,
                reference_number=reference_number,
                posted_by_user_id=posted_by_user_id,
            )
        )


async def reverse_entries(
    db: AsyncSession,
    *,
    source_type: str,
    source_id: int,
    reason: str,
    posted_by_user_id: int,
    reversal_date: date,
) -> None:
    entries = list(
        (
            await db.execute(
                select(LedgerEntry).where(
                    LedgerEntry.source_type == source_type,
                    LedgerEntry.source_id == source_id,
                    LedgerEntry.is_reversal.is_(False),
                )
            )
        ).scalars().all()
    )
    if not entries:
        raise ValueError("Original ledger entries were not found")
    for entry in entries:
        db.add(
            LedgerEntry(
                company_id=entry.company_id,
                branch_id=entry.branch_id,
                group_id=entry.group_id,
                member_id=entry.member_id,
                source_type=f"{source_type}_reversal",
                source_id=source_id,
                entry_type="credit" if entry.entry_type == "debit" else "debit",
                account_code=entry.account_code,
                amount=entry.amount,
                entry_date=reversal_date,
                description=f"Reversal: {reason}",
                reference_number=entry.reference_number,
                is_reversal=True,
                reverses_entry_id=entry.id,
                posted_by_user_id=posted_by_user_id,
            )
        )
