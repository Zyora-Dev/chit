import calendar
from datetime import UTC,date,datetime
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from fastapi import APIRouter,Depends,File,Form,HTTPException,Request,UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import require_owner
from app.api.routes.members import require_company,save_document
from app.core.config import settings
from app.db.session import get_db
from app.models.employee import Employee,EmployeeSalaryStructure
from app.models.payroll import PayrollItem,PayrollRun
from app.models.user import User
from app.schemas.payroll import PayrollApproval,PayrollDaysUpdate,PayrollRunCreate
from app.services.accounting import document_number
from app.services.audit import add_audit
router=APIRouter(prefix="/api/v1/payroll",tags=["Payroll"]);Q=Decimal("0.01")
def money(value):return Decimal(value).quantize(Q,rounding=ROUND_HALF_UP)
def calculate(item):
    total=Decimal(str(item.total_days));payable=Decimal(str(item.payable_days));factor=payable/total if total else Decimal("0");earnings=[item.monthly_basic,item.monthly_hra,item.monthly_allowances,item.monthly_incentives];gross=sum((money(Decimal(str(value))*factor) for value in earnings),Decimal("0"));deductions=money(Decimal(str(item.monthly_employee_pf))*factor)+money(Decimal(str(item.monthly_employee_esi))*factor)+(Decimal(str(item.monthly_professional_tax))+Decimal(str(item.monthly_tds))+Decimal(str(item.monthly_other_deductions)) if payable else Decimal("0"));item.gross_salary=gross;item.total_deductions=money(deductions);item.net_salary=money(gross-deductions)
def aggregate(run):run.employee_count=len(run.items);run.total_gross_salary=sum((i.gross_salary for i in run.items),Decimal("0"));run.total_deductions=sum((i.total_deductions for i in run.items),Decimal("0"));run.total_net_salary=sum((i.net_salary for i in run.items),Decimal("0"))
def serialize(run):return {"id":run.id,"payroll_year":run.payroll_year,"payroll_month":run.payroll_month,"period_start":run.period_start,"period_end":run.period_end,"status":run.status,"employee_count":run.employee_count,"total_gross_salary":run.total_gross_salary,"total_deductions":run.total_deductions,"total_net_salary":run.total_net_salary,"notes":run.notes,"voucher_number":run.voucher_number,"payment_date":run.payment_date,"payment_mode":run.payment_mode,"payment_reference_number":run.payment_reference_number,"payment_proof_file_name":run.payment_proof_file_name,"items":[{"id":i.id,"employee_id":i.employee_id,"employee_code":i.employee_code,"employee_name":i.employee_name,"department":i.department,"designation":i.designation,"total_days":i.total_days,"payable_days":i.payable_days,"lop_days":i.lop_days,"gross_salary":i.gross_salary,"total_deductions":i.total_deductions,"net_salary":i.net_salary} for i in run.items]}
async def load(db,run_id,company_id):
    run=await db.scalar(select(PayrollRun).where(PayrollRun.id==run_id,PayrollRun.company_id==company_id))
    if not run:raise HTTPException(status_code=404,detail="Payroll run not found")
    return run
@router.post("/runs",status_code=201)
async def create_run(payload:PayrollRunCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id)
    if await db.scalar(select(PayrollRun.id).where(PayrollRun.company_id==company.id,PayrollRun.payroll_year==payload.payroll_year,PayrollRun.payroll_month==payload.payroll_month)):raise HTTPException(status_code=409,detail="Payroll already exists for this month")
    last=calendar.monthrange(payload.payroll_year,payload.payroll_month)[1];start=date(payload.payroll_year,payload.payroll_month,1);end=date(payload.payroll_year,payload.payroll_month,last);employees=(await db.execute(select(Employee).where(Employee.company_id==company.id,Employee.is_active.is_(True),Employee.joining_date<=end))).scalars().all();run=PayrollRun(company_id=company.id,payroll_year=payload.payroll_year,payroll_month=payload.payroll_month,period_start=start,period_end=end,notes=payload.notes,created_by_user_id=user.id);db.add(run);await db.flush();missing=[];items=[]
    for employee in employees:
        salary=await db.scalar(select(EmployeeSalaryStructure).where(EmployeeSalaryStructure.employee_id==employee.id,EmployeeSalaryStructure.effective_from<=end).order_by(EmployeeSalaryStructure.effective_from.desc()))
        if not salary:missing.append(employee.employee_code);continue
        item=PayrollItem(payroll_run_id=run.id,company_id=company.id,employee_id=employee.id,salary_structure_id=salary.id,branch_id=employee.branch_id,employee_code=employee.employee_code,employee_name=employee.full_name,department=employee.department,designation=employee.designation,total_days=last,payable_days=last,lop_days=0,monthly_basic=salary.basic,monthly_hra=salary.hra,monthly_allowances=salary.allowances,monthly_incentives=salary.incentives,monthly_employee_pf=salary.employee_pf,monthly_employee_esi=salary.employee_esi,monthly_professional_tax=salary.professional_tax,monthly_tds=salary.tds,monthly_other_deductions=salary.other_deductions,gross_salary=0,total_deductions=0,net_salary=0);calculate(item);items.append(item);db.add(item)
    if missing:await db.rollback();raise HTTPException(status_code=409,detail=f"Salary structure missing for: {', '.join(missing)}")
    run.employee_count=len(items);run.total_gross_salary=sum((i.gross_salary for i in items),Decimal("0"));run.total_deductions=sum((i.total_deductions for i in items),Decimal("0"));run.total_net_salary=sum((i.net_salary for i in items),Decimal("0"));await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="payroll_run",entity_id=run.id,description=f"Created payroll {payload.payroll_month}/{payload.payroll_year}",request=request,new_values={"employee_count":run.employee_count,"net_salary":str(run.total_net_salary)});await db.commit();run=await load(db,run.id,company.id);return serialize(run)
@router.get("/runs")
async def list_runs(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);runs=(await db.execute(select(PayrollRun).where(PayrollRun.company_id==company.id).order_by(PayrollRun.payroll_year.desc(),PayrollRun.payroll_month.desc()))).scalars().all();return [serialize(r) for r in runs]
@router.get("/runs/{run_id}")
async def get_run(run_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);return serialize(await load(db,run_id,company.id))
@router.put("/runs/{run_id}/items/{item_id}/days")
async def update_days(run_id:int,item_id:int,payload:PayrollDaysUpdate,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);run=await load(db,run_id,company.id)
    if run.status!="draft":raise HTTPException(status_code=409,detail="Only draft payroll can be adjusted")
    item=next((i for i in run.items if i.id==item_id),None)
    if not item or payload.payable_days+payload.lop_days!=item.total_days:raise HTTPException(status_code=400,detail="Payable and LOP days must equal total days")
    item.payable_days=payload.payable_days;item.lop_days=payload.lop_days;calculate(item);aggregate(run);await db.commit();return serialize(run)
@router.post("/runs/{run_id}/approve")
async def approve(run_id:int,payload:PayrollApproval,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);run=await load(db,run_id,company.id)
    if run.status!="draft" or not run.items:raise HTTPException(status_code=409,detail="Only non-empty draft payroll can be approved")
    run.status="approved";run.approved_at=datetime.now(UTC);run.approved_by_user_id=user.id;run.approval_notes=payload.approval_notes;add_audit(db,company_id=company.id,user_id=user.id,action="approve",entity_type="payroll_run",entity_id=run.id,description="Approved payroll",request=request,new_values={"status":"approved"});await db.commit();return serialize(run)
@router.post("/runs/{run_id}/pay")
async def pay(run_id:int,request:Request,payment_date:date=Form(),payment_mode:str=Form(),payment_reference_number:str|None=Form(default=None),payment_proof:UploadFile=File(),user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);run=await load(db,run_id,company.id)
    if run.status!="approved":raise HTTPException(status_code=409,detail="Only approved payroll can be paid")
    if payment_mode not in {"cash","upi","bank","cheque"} or payment_mode!="cash" and not payment_reference_number:raise HTTPException(status_code=400,detail="Valid payment mode and reference required")
    root=Path(settings.upload_directory).resolve()/"private"/"payroll"/company.company_code/str(run.id);path,name=await save_document(payment_proof,root/"payment-proof");run.voucher_number=document_number("PAY",company.company_code,payment_date);run.status="paid";run.payment_date=payment_date;run.payment_mode=payment_mode;run.payment_reference_number=payment_reference_number;run.payment_proof_path=path;run.payment_proof_file_name=name;run.paid_by_user_id=user.id;run.paid_at=datetime.now(UTC);add_audit(db,company_id=company.id,user_id=user.id,action="pay",entity_type="payroll_run",entity_id=run.id,description=f"Paid payroll {run.voucher_number}",request=request,new_values={"status":"paid","net_salary":str(run.total_net_salary)});await db.commit();return serialize(run)
@router.get("/runs/{run_id}/payment-proof")
async def proof(run_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);run=await load(db,run_id,company.id)
    if not run.payment_proof_path or not Path(run.payment_proof_path).is_file():raise HTTPException(status_code=404,detail="Payment proof not found")
    return FileResponse(run.payment_proof_path,filename=run.payment_proof_file_name,content_disposition_type="inline")
