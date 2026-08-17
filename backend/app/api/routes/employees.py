import hashlib
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_owner
from app.api.routes.members import require_company, save_document
from app.core.config import settings
from app.db.session import get_db
from app.models.branch import Branch
from app.models.employee import Employee, EmployeeDocument, EmployeeSalaryStructure
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeKycReview, EmployeeListResponse, EmployeeResponse, EmployeeSalaryCreate, EmployeeUpdate
from app.services.audit import add_audit

router=APIRouter(prefix="/api/v1/employees",tags=["Employees"])
DOCUMENT_TYPES={"photo","aadhaar","pan","bank_proof","address_proof","education_certificate","experience_letter","offer_letter","appointment_letter","employment_contract","uan_pf","esic","nominee_form","police_verification","driving_licence","other"}

def digest(value:str)->str:return hashlib.sha256(value.encode()).hexdigest()
def code()->str:return f"EMP-{secrets.token_hex(4).upper()}"

async def load_employee(db,employee_id,company_id):
    employee=await db.scalar(select(Employee).where(Employee.id==employee_id,Employee.company_id==company_id).options(selectinload(Employee.salary_structures),selectinload(Employee.documents)))
    if not employee:raise HTTPException(status_code=404,detail="Employee not found")
    return employee

async def validate_relations(db,company_id,branch_id,manager_id):
    if branch_id and not await db.scalar(select(Branch.id).where(Branch.id==branch_id,Branch.company_id==company_id,Branch.is_active.is_(True))):raise HTTPException(status_code=400,detail="Invalid or inactive branch")
    if manager_id and not await db.scalar(select(Employee.id).where(Employee.id==manager_id,Employee.company_id==company_id,Employee.is_active.is_(True))):raise HTTPException(status_code=400,detail="Invalid reporting manager")

def assign(employee,payload,keep_aadhaar=False):
    data=payload.model_dump(exclude={"aadhaar_number","salary"})
    for key,value in data.items():setattr(employee,key,value)
    if payload.aadhaar_number:
        employee.aadhaar_hash=digest(payload.aadhaar_number);employee.aadhaar_last4=payload.aadhaar_number[-4:]

@router.post("",response_model=EmployeeResponse,status_code=201)
async def create_employee(payload:EmployeeCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await validate_relations(db,company.id,payload.branch_id,payload.reporting_manager_employee_id);employee=Employee(company_id=company.id,employee_code=code());assign(employee,payload);db.add(employee)
    try:
        await db.flush()
        if payload.salary:
            salary_data=payload.salary;gross=salary_data.basic+salary_data.hra+salary_data.allowances+salary_data.incentives;deductions=salary_data.employee_pf+salary_data.employee_esi+salary_data.professional_tax+salary_data.tds+salary_data.other_deductions
            salary=EmployeeSalaryStructure(employee_id=employee.id,**salary_data.model_dump(),gross_salary=gross,net_salary=gross-deductions,created_by_user_id=user.id);db.add(salary);await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="employee_salary",entity_id=salary.id,description=f"Added initial salary for {employee.employee_code}",request=request,new_values={"effective_from":str(salary_data.effective_from),"gross_salary":str(gross),"net_salary":str(gross-deductions)})
        add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="employee",entity_id=employee.id,description=f"Created employee {employee.employee_code}",request=request,new_values={"full_name":employee.full_name,"department":employee.department});await db.commit()
    except IntegrityError as exc:await db.rollback();raise HTTPException(status_code=409,detail="Employee mobile, Aadhaar, PAN, UAN, or code already exists") from exc
    return await load_employee(db,employee.id,company.id)

@router.get("",response_model=EmployeeListResponse)
async def list_employees(search:str|None=None,branch_id:int|None=None,status:str|None=None,kyc_status:str|None=None,include_archived:bool=False,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);filters=[Employee.company_id==company.id]
    if not include_archived:filters.append(Employee.is_active.is_(True))
    if search:term=f"%{search.strip()}%";filters.append(or_(Employee.full_name.ilike(term),Employee.employee_code.ilike(term),Employee.mobile_number.ilike(term),Employee.designation.ilike(term)))
    if branch_id:filters.append(Employee.branch_id==branch_id)
    if status:filters.append(Employee.status==status)
    if kyc_status:filters.append(Employee.kyc_status==kyc_status)
    total=await db.scalar(select(func.count(Employee.id)).where(*filters)) or 0;items=(await db.execute(select(Employee).where(*filters).order_by(Employee.created_at.desc()).offset((page-1)*page_size).limit(page_size))).scalars().all();return EmployeeListResponse(items=list(items),total=total,page=page,page_size=page_size)

@router.get("/{employee_id}",response_model=EmployeeResponse)
async def get_employee(employee_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);return await load_employee(db,employee_id,company.id)

@router.put("/{employee_id}",response_model=EmployeeResponse)
async def update_employee(employee_id:int,payload:EmployeeUpdate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);await validate_relations(db,company.id,payload.branch_id,payload.reporting_manager_employee_id);assign(employee,payload)
    try:add_audit(db,company_id=company.id,user_id=user.id,action="update",entity_type="employee",entity_id=employee.id,description=f"Updated employee {employee.employee_code}",request=request,new_values={"department":employee.department,"designation":employee.designation,"status":employee.status});await db.commit()
    except IntegrityError as exc:await db.rollback();raise HTTPException(status_code=409,detail="Employee identity details conflict with another employee") from exc
    return await load_employee(db,employee.id,company.id)

@router.delete("/{employee_id}",status_code=204)
async def archive_employee(employee_id:int,request:Request,reason:str=Query(min_length=3,max_length=500),user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);employee.is_active=False;employee.status="separated";employee.archived_at=datetime.now(UTC);employee.archived_by_user_id=user.id;employee.archive_reason=reason;add_audit(db,company_id=company.id,user_id=user.id,action="archive",entity_type="employee",entity_id=employee.id,description=f"Archived employee {employee.employee_code}",request=request,new_values={"reason":reason});await db.commit()

@router.post("/{employee_id}/restore",response_model=EmployeeResponse)
async def restore_employee(employee_id:int,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);employee.is_active=True;employee.status="active";employee.archived_at=None;employee.archived_by_user_id=None;employee.archive_reason=None;add_audit(db,company_id=company.id,user_id=user.id,action="restore",entity_type="employee",entity_id=employee.id,description=f"Restored employee {employee.employee_code}",request=request,new_values={"is_active":True});await db.commit();return await load_employee(db,employee.id,company.id)

@router.post("/{employee_id}/salary")
async def add_salary(employee_id:int,payload:EmployeeSalaryCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);current=await db.scalar(select(EmployeeSalaryStructure).where(EmployeeSalaryStructure.employee_id==employee.id,EmployeeSalaryStructure.effective_to.is_(None)).order_by(EmployeeSalaryStructure.effective_from.desc()))
    if current and payload.effective_from<=current.effective_from:raise HTTPException(status_code=409,detail="Salary effective date must follow current structure")
    if current:current.effective_to=payload.effective_from
    gross=payload.basic+payload.hra+payload.allowances+payload.incentives;deductions=payload.employee_pf+payload.employee_esi+payload.professional_tax+payload.tds+payload.other_deductions;salary=EmployeeSalaryStructure(employee_id=employee.id,**payload.model_dump(),gross_salary=gross,net_salary=gross-deductions,created_by_user_id=user.id);db.add(salary);await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="employee_salary",entity_id=salary.id,description=f"Added salary revision for {employee.employee_code}",request=request,new_values={"effective_from":str(payload.effective_from),"gross_salary":str(gross),"net_salary":str(gross-deductions)});await db.commit();return {"id":salary.id,"effective_from":salary.effective_from,"gross_salary":gross,"net_salary":salary.net_salary}

@router.get("/{employee_id}/salary")
async def salary_history(employee_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);return [{"id":s.id,"effective_from":s.effective_from,"effective_to":s.effective_to,"annual_ctc":s.annual_ctc,"basic":s.basic,"hra":s.hra,"allowances":s.allowances,"incentives":s.incentives,"gross_salary":s.gross_salary,"net_salary":s.net_salary} for s in sorted(employee.salary_structures,key=lambda x:x.effective_from,reverse=True)]

@router.post("/{employee_id}/documents",status_code=201)
async def upload_document(employee_id:int,request:Request,document_type:str=Form(),file:UploadFile=File(),user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id)
    if document_type not in DOCUMENT_TYPES:raise HTTPException(status_code=400,detail="Invalid document type")
    root=Path(settings.upload_directory).resolve()/"private"/"employees"/company.company_code/employee.employee_code;path,name=await save_document(file,root/f"{document_type}-{secrets.token_hex(4)}");size=Path(path).stat().st_size;document=EmployeeDocument(employee_id=employee.id,document_type=document_type,file_path=path,original_file_name=name,mime_type=file.content_type or "application/octet-stream",file_size=size,uploaded_by_user_id=user.id);db.add(document);await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="upload",entity_type="employee_document",entity_id=document.id,description=f"Uploaded {document_type} for {employee.employee_code}",request=request,new_values={"document_type":document_type,"file_name":name});await db.commit();return {"id":document.id,"document_type":document_type,"file_name":name,"verification_status":document.verification_status}

@router.get("/{employee_id}/documents")
async def list_documents(employee_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);return [{"id":d.id,"document_type":d.document_type,"file_name":d.original_file_name,"verification_status":d.verification_status,"created_at":d.created_at} for d in employee.documents]

@router.get("/{employee_id}/documents/{document_id}")
async def get_document(employee_id:int,document_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await load_employee(db,employee_id,company.id);document=await db.scalar(select(EmployeeDocument).where(EmployeeDocument.id==document_id,EmployeeDocument.employee_id==employee_id));
    if not document or not Path(document.file_path).is_file():raise HTTPException(status_code=404,detail="Document not found")
    return FileResponse(document.file_path,filename=document.original_file_name,content_disposition_type="inline")

@router.put("/{employee_id}/kyc",response_model=EmployeeResponse)
async def review_kyc(employee_id:int,payload:EmployeeKycReview,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await load_employee(db,employee_id,company.id);types={d.document_type for d in employee.documents}
    if payload.aadhaar_status=="verified" and "aadhaar" not in types:raise HTTPException(status_code=409,detail="Upload Aadhaar evidence first")
    if payload.pan_status=="verified" and "pan" not in types:raise HTTPException(status_code=409,detail="Upload PAN evidence first")
    if payload.bank_status=="verified" and "bank_proof" not in types:raise HTTPException(status_code=409,detail="Upload bank proof first")
    rejected="rejected" in {payload.aadhaar_status,payload.pan_status,payload.bank_status}
    if rejected and not payload.rejection_reason:raise HTTPException(status_code=400,detail="Rejection reason is required")
    employee.aadhaar_verification_status=payload.aadhaar_status;employee.pan_verification_status=payload.pan_status;employee.bank_verification_status=payload.bank_status;employee.kyc_status="rejected" if rejected else "verified";employee.kyc_reviewed_at=datetime.now(UTC);employee.kyc_reviewed_by_user_id=user.id;employee.kyc_rejection_reason=payload.rejection_reason;employee.kyc_notes=payload.notes;add_audit(db,company_id=company.id,user_id=user.id,action="review",entity_type="employee_kyc",entity_id=employee.id,description=f"Reviewed KYC for {employee.employee_code}",request=request,new_values={"kyc_status":employee.kyc_status});await db.commit();return await load_employee(db,employee.id,company.id)
