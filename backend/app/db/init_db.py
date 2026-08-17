import asyncio

import app.models  # noqa: F401
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine


async def create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        for statement in (
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS date_of_birth DATE",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS nominee_name VARCHAR(200)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS nominee_relationship VARCHAR(80)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS nominee_mobile_number VARCHAR(20)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS nominee_date_of_birth DATE",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS bank_account_holder_name VARCHAR(200)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS bank_account_number VARCHAR(34)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS bank_name VARCHAR(150)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS bank_branch_name VARCHAR(150)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS bank_ifsc_code VARCHAR(11)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS bank_account_type VARCHAR(20)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS gender VARCHAR(30)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS kyc_status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS aadhaar_verification_status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS pan_verification_status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS aadhaar_verified_at TIMESTAMPTZ",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS pan_verified_at TIMESTAMPTZ",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS kyc_reviewed_at TIMESTAMPTZ",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS kyc_reviewed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS kyc_rejection_reason VARCHAR(500)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS kyc_notes VARCHAR(1000)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS internal_notes VARCHAR(1000)",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS risk_flags JSON NOT NULL DEFAULT '[]'::json",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS archived_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE members ADD COLUMN IF NOT EXISTS archive_reason VARCHAR(500)",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS max_member_count INTEGER",
            "UPDATE chit_groups SET max_member_count = duration_months WHERE max_member_count IS NULL",
            "ALTER TABLE chit_groups ALTER COLUMN max_member_count SET NOT NULL",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS foreman_commission_percent NUMERIC(5,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS maturity_date DATE",
            "UPDATE chit_groups SET maturity_date = start_date + (duration_months - 1) * INTERVAL '1 month' WHERE maturity_date IS NULL",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS grace_period_days INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS late_fee_type VARCHAR(20) NOT NULL DEFAULT 'none'",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS late_fee_value NUMERIC(14,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS auction_weekday INTEGER",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS auction_time VARCHAR(5)",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS minimum_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS maximum_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 100",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS closed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS cancelled_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE chit_groups ADD COLUMN IF NOT EXISTS cancellation_reason VARCHAR(500)",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS received_amount NUMERIC(14,2)",
            "UPDATE chit_payments SET received_amount = amount WHERE received_amount IS NULL",
            "ALTER TABLE chit_payments ALTER COLUMN received_amount SET NOT NULL",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS late_fee_amount NUMERIC(14,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS penalty_amount NUMERIC(14,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS waiver_amount NUMERIC(14,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS waiver_reason VARCHAR(500)",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS excess_amount NUMERIC(14,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS refunded_amount NUMERIC(14,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS collection_location_text VARCHAR(300)",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS collection_latitude NUMERIC(9,6)",
            "ALTER TABLE chit_payments ADD COLUMN IF NOT EXISTS collection_longitude NUMERIC(9,6)",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS commission_percent NUMERIC(5,2) NOT NULL DEFAULT 0",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS winner_acknowledged_at TIMESTAMPTZ",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS approval_notes VARCHAR(500)",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS payout_date DATE",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS payout_mode VARCHAR(30)",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS payout_reference_number VARCHAR(100)",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS payout_verified_at TIMESTAMPTZ",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS payout_verified_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS settlement_proof_path VARCHAR(500)",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS settlement_proof_file_name VARCHAR(255)",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS cancelled_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "ALTER TABLE chit_auctions ADD COLUMN IF NOT EXISTS cancellation_reason VARCHAR(500)",
            "UPDATE chit_auctions SET status = 'paid', payout_date = auction_date, payout_verified_at = created_at WHERE status = 'settled'",
            "ALTER TABLE chit_group_closures ADD COLUMN IF NOT EXISTS expected_closing_balance NUMERIC(16,2) NOT NULL DEFAULT 0",
        ):
            await connection.execute(text(statement))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
