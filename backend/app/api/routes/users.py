from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import require_owner
from app.api.routes.members import require_company
from app.core.security import hash_password
from app.db.session import get_db
from app.models.agent import CollectionAgent
from app.models.employee import Employee
from app.models.rbac import CompanyUser,Permission,Role
from app.models.user import User
from app.schemas.users import PasswordReset,RoleCreate,UserCredentialCreate,UserStatus
from app.services.audit import add_audit
router=APIRouter(prefix="/api/v1/admin",tags=["Users & Roles"])
PERMISSIONS={"dashboard.view":"Dashboard","members.view":"Members","members.manage":"Members","schemes.view":"Schemes","schemes.manage":"Schemes","collections.view":"Collections","collections.record":"Collections","collections.refund":"Collections","auctions.view":"Auctions","auctions.manage":"Auctions","employees.view":"Employees","employees.manage":"Employees","payroll.view":"Payroll","payroll.manage":"Payroll","agents.manage":"Collection Agents","ledger.view":"Accounting","audit.view":"Audit","company.manage":"Company"}
AGENT_CODES=["agent.check_in","agent.location","agent.assignments","agent.collect","agent.receipt"]
async def ensure_permissions(db):
    existing={p.code:p for p in (await db.execute(select(Permission))).scalars().all()}
    for code,module in {**PERMISSIONS,**{c:"Agent" for c in AGENT_CODES}}.items():
        if code not in existing:db.add(Permission(code=code,module=module,name=code.replace("."," ").title()))
    await db.flush()
async def ensure_agent_role(db,company,user_id):
    await ensure_permissions(db);role=await db.scalar(select(Role).where(Role.company_id==company.id,Role.name=="Collection Agent"))
    if not role:role=Role(company_id=company.id,name="Collection Agent",description="Fixed collection-only mobile role",is_system=True,created_by_user_id=user_id);role.permissions=list((await db.execute(select(Permission).where(Permission.code.in_(AGENT_CODES)))).scalars().all());db.add(role);await db.flush()
    return role
@router.get("/permissions")
async def permissions(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    await require_company(db,user.id);await ensure_permissions(db);await db.commit();return [{"code":p.code,"module":p.module,"name":p.name} for p in (await db.execute(select(Permission).order_by(Permission.module,Permission.code))).scalars().all() if p.code not in AGENT_CODES]
@router.post("/roles",status_code=201)
async def create_role(payload:RoleCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await ensure_permissions(db)
    if payload.name.lower()=="collection agent":raise HTTPException(status_code=409,detail="Collection Agent is a fixed system role")
    permissions=list((await db.execute(select(Permission).where(Permission.code.in_(payload.permission_codes),Permission.code.not_in(AGENT_CODES)))).scalars().all())
    if len(permissions)!=len(set(payload.permission_codes)):raise HTTPException(status_code=400,detail="Invalid permission selection")
    role=Role(company_id=company.id,name=payload.name.strip(),description=payload.description,created_by_user_id=user.id,permissions=permissions);db.add(role);await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="role",entity_id=role.id,description=f"Created role {role.name}",request=request,new_values={"permissions":payload.permission_codes});await db.commit();return {"id":role.id,"name":role.name,"permission_codes":[p.code for p in role.permissions],"is_system":role.is_system}
@router.get("/roles")
async def list_roles(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await ensure_agent_role(db,company,user.id);await db.commit();roles=(await db.execute(select(Role).where(Role.company_id==company.id,Role.is_active.is_(True)).order_by(Role.name))).scalars().all();return [{"id":r.id,"name":r.name,"description":r.description,"is_system":r.is_system,"permission_codes":[p.code for p in r.permissions]} for r in roles]
@router.post("/users",status_code=201)
async def create_user(payload:UserCredentialCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await db.scalar(select(Employee).where(Employee.id==payload.employee_id,Employee.company_id==company.id,Employee.is_active.is_(True)));role=await db.scalar(select(Role).where(Role.id==payload.role_id,Role.company_id==company.id,Role.is_active.is_(True)))
    if not employee or not role:raise HTTPException(status_code=400,detail="Invalid employee or role")
    if await db.scalar(select(CompanyUser.id).where(CompanyUser.employee_id==employee.id)):raise HTTPException(status_code=409,detail="Employee already has credentials")
    account=User(email=employee.personal_email or employee.official_email or f"{employee.employee_code.lower()}@local.zchit",login_id=employee.employee_code,password_hash=hash_password(payload.password),role="collection_agent" if role.name=="Collection Agent" else "staff",is_verified=True,is_active=True);db.add(account);await db.flush();link=CompanyUser(company_id=company.id,user_id=account.id,employee_id=employee.id,role_id=role.id,branch_id=payload.branch_id or employee.branch_id);db.add(link);await db.flush()
    if role.name=="Collection Agent":
        if not employee.collection_agent_enabled:raise HTTPException(status_code=409,detail="Enable collection agent on employee first")
        db.add(CollectionAgent(company_id=company.id,employee_id=employee.id,user_id=account.id,created_by_user_id=user.id))
    add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="user",entity_id=account.id,description=f"Created credentials for {employee.employee_code}",request=request,new_values={"login_id":employee.employee_code,"role":role.name});await db.commit();return {"id":account.id,"login_id":employee.employee_code,"employee_name":employee.full_name,"role":role.name,"is_active":True}
@router.get("/users")
async def list_users(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);records=(await db.execute(select(CompanyUser,User,Employee,Role).join(User,CompanyUser.user_id==User.id).join(Employee,CompanyUser.employee_id==Employee.id).join(Role,CompanyUser.role_id==Role.id).where(CompanyUser.company_id==company.id).order_by(Employee.full_name))).all();return [{"id":account.id,"login_id":account.login_id,"employee_id":employee.id,"employee_code":employee.employee_code,"employee_name":employee.full_name,"role_id":role.id,"role_name":role.name,"branch_id":link.branch_id,"is_active":account.is_active} for link,account,employee,role in records]
@router.put("/users/{user_id}/status")
async def status(user_id:int,payload:UserStatus,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);record=(await db.execute(select(CompanyUser,User).join(User,CompanyUser.user_id==User.id).where(CompanyUser.company_id==company.id,User.id==user_id))).one_or_none()
    if not record:raise HTTPException(status_code=404,detail="User not found")
    link,account=record;account.is_active=payload.is_active;link.is_active=payload.is_active;agent=await db.scalar(select(CollectionAgent).where(CollectionAgent.user_id==account.id));
    if agent:agent.status="active" if payload.is_active else "disabled"
    add_audit(db,company_id=company.id,user_id=user.id,action="activate" if payload.is_active else "deactivate",entity_type="user",entity_id=account.id,description="Updated user status",request=request,new_values={"is_active":payload.is_active});await db.commit();return {"is_active":account.is_active}
@router.put("/users/{user_id}/password")
async def reset_password(user_id:int,payload:PasswordReset,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);account=await db.scalar(select(User).join(CompanyUser,CompanyUser.user_id==User.id).where(User.id==user_id,CompanyUser.company_id==company.id))
    if not account:raise HTTPException(status_code=404,detail="User not found")
    account.password_hash=hash_password(payload.password);add_audit(db,company_id=company.id,user_id=user.id,action="reset_password",entity_type="user",entity_id=account.id,description="Owner reset user password",request=request);await db.commit();return {"message":"Password reset"}
