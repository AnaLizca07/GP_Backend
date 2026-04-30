from fastapi import APIRouter, Depends, HTTPException, status

from app.models.auth import UserResponse
from app.services.kpis import kpi_service
from app.database import get_admin_supabase

from app.api.deps import get_current_user

router = APIRouter(tags=["kpis"])

@router.get("/kpis/performance-indices")
async def get_performance_indices(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    SPI y CPI por proyecto para la vista global del gerente.
    Acceso: solo managers.
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden ver los índices de desempeño",
        )
    return await kpi_service.get_performance_indices(user_id=current_user.id)

@router.get("/projects/{project_id}/kpis")
async def get_project_kpis(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    KPIs completos del proyecto: avance de tareas, fechas, equipo, presupuesto.
    Acceso: solo managers.
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden ver los KPIs del proyecto",
        )

    data = await kpi_service.get_project_kpis(project_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    return data

@router.get("/projects/{project_id}/sponsor-progress")
async def get_sponsor_progress(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Vista de progreso del proyecto para el sponsor.
    Acceso: managers (cualquier proyecto) o sponsors (sus proyectos).
    """
    if current_user.role not in ("manager", "sponsor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta vista",
        )

    if current_user.role == "manager":
        # Manager puede ver cualquier proyecto — usar get_project_kpis simplificado
        data = await kpi_service.get_project_kpis(project_id)
        if data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado",
            )
        return data

    # Sponsor
    data = await kpi_service.get_sponsor_progress(project_id, current_user.id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado o sin acceso",
        )
    return data

@router.get("/employees/{employee_id}/performance")
async def get_employee_performance(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Métricas de desempeño de un empleado.
    Acceso: manager (cualquier empleado) o el propio empleado.
    """
    if current_user.role not in ("manager", "employee"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta información",
        )

    if current_user.role == "employee":
        # Verify the employee is requesting their own data
        sb = get_admin_supabase()
        emp_res = sb.table("employees").select("id").eq("user_id", current_user.id).execute()
        own_id = emp_res.data[0]["id"] if emp_res.data else None
        if own_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes ver tu propio desempeño",
            )

    data = await kpi_service.get_employee_performance(employee_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empleado no encontrado",
        )
    return data

@router.get("/projects/{project_id}/employee-performance")
async def get_project_employee_performance(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Desempeño por empleado dentro de un proyecto.
    Acceso: managers (cualquier proyecto) o sponsors (sus proyectos).
    """
    if current_user.role not in ("manager", "sponsor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta información",
        )

    if current_user.role == "sponsor":
        sb = get_admin_supabase()
        proj_res = sb.table("projects").select("id").eq("id", project_id).eq("sponsor_id", current_user.id).execute()
        if not proj_res.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes ver el desempeño de los proyectos que patrocinas",
            )

    data = await kpi_service.get_project_employee_performance(project_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    return data

@router.get("/employees/{employee_id}/performance/sponsor")
async def get_employee_performance_for_sponsor(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Métricas de desempeño de un empleado.
    Acceso: sponsors (empleados en sus proyectos).
    """
    if current_user.role != "sponsor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint exclusivo para patrocinadores",
        )

    sb = get_admin_supabase()
    # Verificar que el empleado pertenece a un proyecto del sponsor
    emp_proj = sb.table("project_employees").select("project_id, projects(sponsor_id)").eq("employee_id", employee_id).execute()
    sponsor_projects = [row for row in (emp_proj.data or []) if row.get("projects", {}).get("sponsor_id") == current_user.id]
    if not sponsor_projects:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes ver empleados de tus proyectos",
        )

    data = await kpi_service.get_employee_performance(employee_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empleado no encontrado",
        )
    return data

@router.get("/projects/{project_id}/budget-summary")
async def get_project_budget_summary(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Resumen de presupuesto de un proyecto: total, gastado, restante y % consumido.
    Acceso: managers (cualquier proyecto) o sponsors (sus proyectos).
    """
    if current_user.role not in ("manager", "sponsor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta información",
        )

    sb = get_admin_supabase()

    # Verificar acceso del sponsor
    if current_user.role == "sponsor":
        proj_check = sb.table("projects").select("id").eq("id", project_id).eq("sponsor_id", current_user.id).execute()
        if not proj_check.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes ver el presupuesto de tus proyectos",
            )

    # Obtener presupuesto total
    proj_res = sb.table("projects").select("id, name, budget").eq("id", project_id).execute()
    if not proj_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    project = proj_res.data[0]
    total_budget = float(project.get("budget") or 0)

    # Transacciones del proyecto
    tx_res = sb.table("transactions").select("type, amount").eq("project_id", project_id).execute()
    rows = tx_res.data or []
    spent = sum(float(r["amount"]) for r in rows if r["type"] == "expense")
    income = sum(float(r["amount"]) for r in rows if r["type"] == "income")
    # Saldo real = dinero efectivamente recibido - gastos (NO depende del presupuesto total)
    available_balance = income - spent
    # Presupuesto restante = referencia del contrato (cuánto queda por cobrar/gastar del total pactado)
    budget_remaining = max(0.0, total_budget - spent)
    consumed_pct = round(spent / total_budget * 100, 1) if total_budget > 0 else 0.0

    return {
        "project_id": project_id,
        "project_name": project["name"],
        "total_budget": total_budget,
        "spent": spent,
        "income": income,
        "available_balance": available_balance,   # saldo real: ingresos - egresos
        "remaining": budget_remaining,            # presupuesto no consumido (referencia)
        "consumed_percentage": consumed_pct,
    }
