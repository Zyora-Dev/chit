from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


class ChitCreate(BaseModel):
    scheme_name: str = Field(min_length=2, max_length=200)
    scheme_amount: Decimal = Field(gt=0)
    start_date: date
    duration_months: int = Field(ge=2, le=120)
    max_member_count: int | None = Field(default=None, ge=1, le=1000)
    foreman_commission_percent: Decimal = Field(default=0, ge=0, le=100)
    grace_period_days: int = Field(default=0, ge=0, le=365)
    late_fee_type: str = Field(default="none", pattern=r"^(none|fixed|percentage)$")
    late_fee_value: Decimal = Field(default=0, ge=0)
    auction_weekday: int | None = Field(default=None,ge=0,le=6)
    auction_time: str | None = Field(default=None,pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    minimum_discount_percent: Decimal = Field(default=0,ge=0,le=100)
    maximum_discount_percent: Decimal = Field(default=100,ge=0,le=100)


class ScheduleUpdate(BaseModel):
    id: int
    due_date: date
    payable_amount: Decimal = Field(ge=0)
    receivable_amount: Decimal = Field(ge=0)


class ScheduleBulkUpdate(BaseModel):
    schedules: list[ScheduleUpdate] = Field(min_length=1)


class EnrollmentUpdate(BaseModel):
    member_ids: list[int] = Field(min_length=1)


class EnrollmentReplace(BaseModel):
    replacement_member_id: int
    effective_installment: int = Field(ge=1)
    effective_date: date
    reason: str = Field(min_length=3, max_length=500)
    old_member_acknowledged: bool
    new_member_acknowledged: bool


class EnrollmentTransferApproval(BaseModel):
    approval_notes: str | None = Field(default=None, max_length=500)


class EnrollmentTransferResponse(BaseModel):
    id: int; group_id: int; old_enrollment_id: int; old_member_id: int
    old_member_name: str; replacement_member_id: int; replacement_member_name: str
    new_enrollment_id: int | None; effective_installment: int; effective_date: date
    outstanding_balance: Decimal; reason: str; status: str
    old_member_acknowledged_at: datetime | None; new_member_acknowledged_at: datetime | None
    old_member_consent_file_name: str | None; new_member_consent_file_name: str | None
    requested_at: datetime; approved_at: datetime | None; approval_notes: str | None


class PaymentCreate(BaseModel):
    member_id: int
    schedule_id: int
    amount: Decimal = Field(gt=0)
    received_amount: Decimal | None = Field(default=None, gt=0)
    late_fee_amount: Decimal = Field(default=0, ge=0)
    penalty_amount: Decimal = Field(default=0, ge=0)
    waiver_amount: Decimal = Field(default=0, ge=0)
    waiver_reason: str | None = Field(default=None, max_length=500)
    excess_amount: Decimal = Field(default=0, ge=0)
    collection_location_text: str | None = Field(default=None, max_length=300)
    collection_latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    collection_longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    payment_date: date
    payment_mode: str = Field(pattern=r"^(cash|upi|bank|cheque)$")
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    branch_id: int | None = None
    payment_source: str = Field(default="manual", pattern=r"^(manual|agent|online|bank_import)$")


class ScheduleResponse(BaseModel):
    id: int; installment_number: int; due_date: date
    payable_amount: Decimal; receivable_amount: Decimal
    model_config = {"from_attributes": True}


class EnrolledMemberResponse(BaseModel):
    enrollment_id: int; member_id: int; member_code: str; full_name: str; mobile_number: str
    start_installment: int; end_installment: int | None; status: str
    replaced_enrollment_id: int | None; break_reason: str | None


class ChitResponse(BaseModel):
    id: int; group_code: str; scheme_name: str; scheme_amount: Decimal; start_date: date
    duration_months: int; max_member_count: int; active_member_count: int
    available_slot_count: int; foreman_commission_percent: Decimal
    maturity_date: date | None; grace_period_days: int; late_fee_type: str; late_fee_value: Decimal
    status: str; schedules: list[ScheduleResponse]
    members: list[EnrolledMemberResponse]; created_at: datetime


class PaymentResponse(BaseModel):
    id: int; member_id: int; member_name: str; schedule_id: int; installment_number: int
    amount: Decimal; payment_date: date; payment_mode: str; reference_number: str | None
    received_amount: Decimal; late_fee_amount: Decimal; penalty_amount: Decimal
    waiver_amount: Decimal; excess_amount: Decimal; refunded_amount: Decimal
    receipt_number: str | None = None; branch_id: int | None = None
    payment_source: str = "manual"; status: str = "posted"


class AuctionCreate(BaseModel):
    schedule_id: int
    winner_member_id: int
    auction_date: date
    bid_amount: Decimal = Field(gt=0)
    discount_amount: Decimal = Field(ge=0)
    notes: str | None = Field(default=None, max_length=500)
    branch_id: int | None = None


class AuctionResponse(BaseModel):
    id: int; group_id: int; group_code: str; scheme_name: str
    schedule_id: int; installment_number: int; due_date: date
    winner_member_id: int; winner_name: str; auction_date: date
    bid_amount: Decimal; discount_amount: Decimal; commission_amount: Decimal; commission_percent: Decimal
    payout_amount: Decimal; settled_installment_amount: Decimal
    net_payout_amount: Decimal; status: str; notes: str | None
    voucher_number: str | None = None; branch_id: int | None = None
    winner_acknowledged_at: datetime | None = None; approved_at: datetime | None = None
    approval_notes: str | None = None; payout_date: date | None = None
    payout_mode: str | None = None; payout_reference_number: str | None = None
    payout_verified_at: datetime | None = None; settlement_proof_file_name: str | None = None


class AuctionApproval(BaseModel):
    winner_acknowledged: bool
    approval_notes: str | None = Field(default=None, max_length=500)


class AuctionPayout(BaseModel):
    payout_date: date
    payout_mode: str = Field(pattern=r"^(cash|upi|bank|cheque)$")
    payout_reference_number: str | None = Field(default=None, max_length=100)
    payout_verified: bool


class AuctionBidCreate(BaseModel):
    bidder_member_id: int
    bid_amount: Decimal = Field(gt=0)
    discount_amount: Decimal = Field(ge=0)


class CancellationCreate(BaseModel):
    reason: str = Field(min_length=3,max_length=500)


class SchemeClose(BaseModel):
    actual_closing_balance: Decimal
    variance_reason: str | None = Field(default=None, max_length=500)


class RefundCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    refund_date: date
    refund_mode: str = Field(pattern=r"^(cash|upi|bank|cheque)$")
    reference_number: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=3, max_length=500)


class MemberLedgerRow(BaseModel):
    schedule_id: int; installment_number: int; due_date: date
    payable_amount: Decimal; receivable_amount: Decimal
    status: str; paid_amount: Decimal | None = None; payment_date: date | None = None
    balance_amount: Decimal | None = None
    payment_mode: str | None = None; reference_number: str | None = None
    auction_id: int | None = None; payout_amount: Decimal | None = None
    net_payout_amount: Decimal | None = None


class MemberLedgerResponse(BaseModel):
    group_id: int; group_code: str; scheme_name: str
    member_id: int; member_code: str; member_name: str; mobile_number: str
    rows: list[MemberLedgerRow]


class CollectionReportRow(BaseModel):
    payment_id: int; payment_date: date; amount: Decimal; payment_mode: str
    received_amount: Decimal; late_fee_amount: Decimal; penalty_amount: Decimal
    waiver_amount: Decimal; waiver_reason: str | None; excess_amount: Decimal
    refunded_amount: Decimal; net_received_amount: Decimal
    reference_number: str | None; notes: str | None
    group_id: int; group_code: str; scheme_name: str
    member_id: int; member_code: str; member_name: str; mobile_number: str
    installment_number: int; due_date: date; payable_amount: Decimal
    receipt_number: str | None = None; status: str = "posted"
    branch_id: int | None = None; branch_code: str | None = None; branch_name: str | None = None
    collected_by_user_id: int | None = None; collector_email: str | None = None; payment_source: str
    collection_location_text: str | None = None
    collection_latitude: Decimal | None = None; collection_longitude: Decimal | None = None


class CollectionModeSummary(BaseModel):
    payment_mode: str; count: int; amount: Decimal


class CollectionDailySummary(BaseModel):
    date: date; count: int; amount: Decimal


class CollectionReportResponse(BaseModel):
    rows: list[CollectionReportRow]
    total_amount: Decimal; total_transactions: int; unique_members: int; schemes_count: int
    total_received_amount: Decimal; total_refunded_amount: Decimal; net_received_amount: Decimal
    mode_summary: list[CollectionModeSummary]
    daily_summary: list[CollectionDailySummary]


class ReversalCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class LedgerEntryResponse(BaseModel):
    id: int; source_type: str; source_id: int; entry_type: str; account_code: str
    amount: Decimal; entry_date: date; description: str; reference_number: str | None
    is_reversal: bool; reverses_entry_id: int | None; created_at: datetime
    model_config = {"from_attributes": True}


class PaymentReceiptResponse(BaseModel):
    payment: PaymentResponse
    company_name: str; company_code: str; company_address: str | None
    scheme_name: str; group_code: str; member_name: str; member_code: str; mobile_number: str
    installment_number: int; due_date: date; payable_amount: Decimal
    total_paid: Decimal; balance_amount: Decimal


class AuctionVoucherResponse(BaseModel):
    auction: AuctionResponse
    company_name: str; company_code: str; company_address: str | None
    member_code: str; mobile_number: str


class ChitDetailResponse(ChitResponse):
    payments: list[PaymentResponse]
    auctions: list[AuctionResponse]
