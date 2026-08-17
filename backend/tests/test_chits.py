from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.chit import AuctionBid, ChitAuction, ChitEnrollmentTransfer, ChitGroup, LedgerEntry
from app.models.company import Company
from app.models.member import Member
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value: yield value


@pytest.mark.asyncio
async def test_complete_chit_scheme_lifecycle(client: AsyncClient):
    email = "chit-test-owner@example.com"
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, password_hash=hash_password("StrongPassword123!"), role="owner", is_verified=True); db.add(user); await db.commit(); await db.refresh(user)
        company = await db.scalar(select(Company).where(Company.owner_id == user.id))
        if not company:
            company = Company(company_code="ZCH-CHITTEST", owner_id=user.id, name="Chit Test", mobile_number="+919999999998", email=email); db.add(company); await db.commit(); await db.refresh(company)
        member = await db.scalar(select(Member).where(Member.company_id == company.id, Member.member_code == "MEM-CHITTEST"))
        if not member:
            member = Member(company_id=company.id, member_code="MEM-CHITTEST", full_name="Chit Member", mobile_number="+919876543212", aadhaar_hash="a" * 64, aadhaar_last4="1234", address_line_1="Test", city="Nagercoil", state="Tamil Nadu", postal_code="629001"); db.add(member); await db.commit(); await db.refresh(member)
        replacement = await db.scalar(select(Member).where(Member.company_id == company.id, Member.member_code == "MEM-CHITREPLACE"))
        if not replacement:
            replacement = Member(company_id=company.id, member_code="MEM-CHITREPLACE", full_name="Replacement Member", mobile_number="+919876543213", aadhaar_hash="b" * 64, aadhaar_last4="5678", address_line_1="Test", city="Nagercoil", state="Tamil Nadu", postal_code="629001"); db.add(replacement); await db.commit(); await db.refresh(replacement)
        group_ids = select(ChitGroup.id).where(ChitGroup.company_id == company.id)
        await db.execute(delete(AuctionBid).where(AuctionBid.auction_id.in_(select(ChitAuction.id).where(ChitAuction.group_id.in_(group_ids)))))
        await db.execute(delete(ChitEnrollmentTransfer).where(ChitEnrollmentTransfer.group_id.in_(group_ids)))
        await db.execute(delete(ChitGroup).where(ChitGroup.company_id == company.id)); await db.commit()
        token = create_access_token(user.id, user.role); company_id = company.id; user_id = user.id; member_id = member.id; replacement_id = replacement.id
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = await client.post("/api/v1/chits", headers=headers, json={"scheme_name":"Gold 12","scheme_amount":120000,"start_date":"2026-09-15","duration_months":12})
        assert response.status_code == 201, response.text
        group = response.json(); group_id = group["id"]
        assert len(group["schedules"]) == 12 and float(group["schedules"][0]["payable_amount"]) == 10000
        rows = group["schedules"]
        rows[0]["payable_amount"] = "9500.00"; rows[0]["receivable_amount"] = "90000.00"
        rows[1]["receivable_amount"] = "90000.00"
        response = await client.put(f"/api/v1/chits/{group_id}/schedule", headers=headers, json={"schedules": rows})
        assert response.status_code == 200 and float(response.json()["schedules"][0]["payable_amount"]) == 9500
        response = await client.put(f"/api/v1/chits/{group_id}/members", headers=headers, json={"member_ids":[member_id]})
        assert response.status_code == 200 and response.json()["status"] == "active"
        response = await client.post(f"/api/v1/chits/{group_id}/payments", headers=headers, json={"member_id":member_id,"schedule_id":rows[0]["id"],"amount":4000,"payment_date":str(date.today()),"payment_mode":"upi","reference_number":"UPI-PART-1","payment_source":"manual"})
        assert response.status_code == 201 and len(response.json()["payments"]) == 1
        first_payment = response.json()["payments"][0]
        assert first_payment["receipt_number"]
        response = await client.post(f"/api/v1/chits/{group_id}/payments", headers=headers, json={"member_id":member_id,"schedule_id":rows[0]["id"],"amount":5500,"payment_date":str(date.today()),"payment_mode":"cash","reference_number":"CASH-PART-2","payment_source":"manual"})
        assert response.status_code == 201 and len(response.json()["payments"]) == 2
        second_payment = next(item for item in response.json()["payments"] if item["id"] != first_payment["id"])
        assert second_payment["receipt_number"] != first_payment["receipt_number"]
        response = await client.post(f"/api/v1/chits/{group_id}/auctions", headers=headers, json={"schedule_id":rows[1]["id"],"winner_member_id":member_id,"auction_date":str(date.today()),"bid_amount":90000,"discount_amount":30000,"notes":"Test settlement"})
        assert response.status_code == 201, response.text
        assert len(response.json()["auctions"]) == 1
        auction = response.json()["auctions"][0]
        assert auction["status"] == "pending" and auction["voucher_number"] is None
        assert float(auction["settled_installment_amount"]) == 10000
        assert float(auction["net_payout_amount"]) == 80000
        approved = await client.post(f"/api/v1/chits/{group_id}/auctions/{auction['id']}/approve", headers=headers, json={"winner_acknowledged":True,"approval_notes":"Winner acknowledged in person"})
        assert approved.status_code == 200, approved.text
        auction = approved.json()["auctions"][0]
        assert auction["status"] == "approved" and auction["winner_acknowledged_at"]
        paid = await client.post(
            f"/api/v1/chits/{group_id}/auctions/{auction['id']}/pay", headers=headers,
            data={"payout_date":str(date.today()),"payout_mode":"bank","payout_reference_number":"BANK-PAYOUT-1","payout_verified":"true"},
            files={"settlement_proof":("settlement.pdf", b"%PDF-1.4\nsettlement proof", "application/pdf")},
        )
        assert paid.status_code == 200, paid.text
        auction = paid.json()["auctions"][0]
        assert auction["status"] == "paid" and auction["voucher_number"]
        assert auction["settlement_proof_file_name"] == "settlement.pdf"
        blocked = await client.post(f"/api/v1/chits/{group_id}/payments", headers=headers, json={"member_id":member_id,"schedule_id":rows[1]["id"],"amount":10000,"payment_date":str(date.today()),"payment_mode":"cash"})
        assert blocked.status_code == 409
        ledger = await client.get(f"/api/v1/chits/{group_id}/members/{member_id}/ledger", headers=headers)
        assert ledger.status_code == 200
        assert ledger.json()["rows"][0]["status"] == "paid"
        assert ledger.json()["rows"][1]["status"] == "settled_against_payout"
        auctions = await client.get("/api/v1/chits/auctions/all", headers=headers)
        assert auctions.status_code == 200 and len(auctions.json()) == 1
        filtered_auctions = await client.get(
            f"/api/v1/chits/auctions/all?scheme_id={group_id}&member_id={member_id}&date_from={date.today()}&date_to={date.today()}&status=paid",
            headers=headers,
        )
        assert filtered_auctions.status_code == 200
        assert len(filtered_auctions.json()) == 1
        assert filtered_auctions.json()[0]["winner_name"] == "Chit Member"
        report = await client.get(
            f"/api/v1/chits/collections/report?scheme_id={group_id}&member_id={member_id}&date_from={date.today()}&date_to={date.today()}&payment_mode=upi",
            headers=headers,
        )
        assert report.status_code == 200, report.text
        report_data = report.json()
        assert report_data["total_transactions"] == 1
        assert float(report_data["total_amount"]) == 4000
        assert report_data["unique_members"] == 1
        assert report_data["schemes_count"] == 1
        assert report_data["rows"][0]["scheme_name"] == "Gold 12"
        assert report_data["rows"][0]["member_name"] == "Chit Member"
        assert report_data["mode_summary"][0]["payment_mode"] == "upi"
        assert report_data["daily_summary"][0]["count"] == 1
        receipt = await client.get(f"/api/v1/chits/receipts/payments/{first_payment['id']}", headers=headers)
        assert receipt.status_code == 200
        assert float(receipt.json()["total_paid"]) == 9500
        assert float(receipt.json()["balance_amount"]) == 0
        voucher = await client.get(f"/api/v1/chits/vouchers/auctions/{auction['id']}", headers=headers)
        assert voucher.status_code == 200 and voucher.json()["auction"]["voucher_number"]
        proof = await client.get(f"/api/v1/chits/{group_id}/auctions/{auction['id']}/settlement-proof", headers=headers)
        assert proof.status_code == 200 and proof.content.startswith(b"%PDF-")
        ledger_entries = await client.get(f"/api/v1/chits/ledger/entries?scheme_id={group_id}", headers=headers)
        assert ledger_entries.status_code == 200
        debit_total = sum(float(item["amount"]) for item in ledger_entries.json() if item["entry_type"] == "debit")
        credit_total = sum(float(item["amount"]) for item in ledger_entries.json() if item["entry_type"] == "credit")
        assert debit_total == credit_total
        detail = await client.get(f"/api/v1/chits/{group_id}", headers=headers)
        enrollment_id = next(item["enrollment_id"] for item in detail.json()["members"] if item["member_id"] == member_id)
        replaced = await client.post(
            f"/api/v1/chits/{group_id}/enrollments/{enrollment_id}/replace",
            headers=headers,
            data={"replacement_member_id":replacement_id,"effective_installment":3,"effective_date":rows[2]["due_date"],"reason":"Member requested transfer","old_member_acknowledged":"true","new_member_acknowledged":"true"},
            files={"old_member_consent":("old-consent.pdf",b"%PDF-1.4\nold consent","application/pdf"),"new_member_consent":("new-consent.pdf",b"%PDF-1.4\nnew consent","application/pdf")},
        )
        assert replaced.status_code == 201, replaced.text
        transfer = replaced.json()
        assert transfer["status"] == "pending" and float(transfer["outstanding_balance"]) == 0
        assert transfer["old_member_consent_file_name"] == "old-consent.pdf"
        approved_transfer = await client.post(f"/api/v1/chits/{group_id}/transfers/{transfer['id']}/approve",headers=headers,json={"approval_notes":"Both consent documents verified"})
        assert approved_transfer.status_code == 200, approved_transfer.text
        old_enrollment = next(item for item in approved_transfer.json()["members"] if item["member_id"] == member_id)
        new_enrollment = next(item for item in approved_transfer.json()["members"] if item["member_id"] == replacement_id)
        assert old_enrollment["status"] == "discontinued" and old_enrollment["end_installment"] == 2
        assert new_enrollment["status"] == "active" and new_enrollment["start_installment"] == 3
        old_blocked = await client.post(f"/api/v1/chits/{group_id}/payments", headers=headers, json={"member_id":member_id,"schedule_id":rows[2]["id"],"amount":10000,"payment_date":str(date.today()),"payment_mode":"cash"})
        assert old_blocked.status_code == 409
        new_paid = await client.post(f"/api/v1/chits/{group_id}/payments", headers=headers, json={"member_id":replacement_id,"schedule_id":rows[2]["id"],"amount":10000,"payment_date":str(date.today()),"payment_mode":"cash"})
        assert new_paid.status_code == 201
        old_ledger = await client.get(f"/api/v1/chits/{group_id}/members/{member_id}/ledger", headers=headers)
        new_ledger = await client.get(f"/api/v1/chits/{group_id}/members/{replacement_id}/ledger", headers=headers)
        assert len(old_ledger.json()["rows"]) == 2 and len(new_ledger.json()["rows"]) == 10
        summary = await client.get(f"/api/v1/members/{member_id}/financial-summary", headers=headers)
        assert summary.status_code == 200
        assert summary.json()["payment_count"] == 2 and summary.json()["auction_settlement_count"] == 1
        reversed_payment = await client.post(f"/api/v1/chits/receipts/payments/{first_payment['id']}/reverse", headers=headers, json={"reason":"Incorrect UPI posting"})
        assert reversed_payment.status_code == 200 and reversed_payment.json()["payment"]["status"] == "reversed"
        reversed_auction = await client.post(f"/api/v1/chits/vouchers/auctions/{auction['id']}/reverse", headers=headers, json={"reason":"Settlement correction"})
        assert reversed_auction.status_code == 200 and reversed_auction.json()["auction"]["status"] == "reversed"
        ledger_after_reversal = await client.get(f"/api/v1/chits/ledger/entries?scheme_id={group_id}", headers=headers)
        assert any(item["is_reversal"] for item in ledger_after_reversal.json())
        second = await client.post("/api/v1/chits", headers=headers, json={"scheme_name":"Gold 12","scheme_amount":100000,"start_date":"2026-10-01","duration_months":10})
        assert second.status_code == 201
        assert second.json()["group_code"] != group["group_code"]
        listing = await client.get("/api/v1/chits", headers=headers)
        assert listing.status_code == 200 and len(listing.json()) == 2
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(LedgerEntry).where(LedgerEntry.company_id == company_id)); await db.commit()
            await db.execute(delete(AuctionBid).where(AuctionBid.auction_id.in_(select(ChitAuction.id).where(ChitAuction.group_id.in_(select(ChitGroup.id).where(ChitGroup.company_id == company_id)))))); await db.commit()
            await db.execute(delete(ChitEnrollmentTransfer).where(ChitEnrollmentTransfer.group_id.in_(select(ChitGroup.id).where(ChitGroup.company_id == company_id)))); await db.commit()
            await db.execute(delete(ChitGroup).where(ChitGroup.company_id == company_id)); await db.commit()
            member = await db.get(Member, member_id)
            if member and member.member_code == "MEM-CHITTEST": await db.delete(member); await db.commit()
            replacement = await db.get(Member, replacement_id)
            if replacement and replacement.member_code == "MEM-CHITREPLACE": await db.delete(replacement); await db.commit()
            company = await db.get(Company, company_id)
            if company and company.company_code == "ZCH-CHITTEST": await db.delete(company); await db.commit()
            user = await db.get(User, user_id)
            if user and user.email == email: await db.delete(user); await db.commit()
