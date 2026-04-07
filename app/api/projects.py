from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List

from app.models.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectEmployeeAssign,
    ProjectEmployeeResponse,
    ProjectStatsResponse
)
from app.models.auth import UserResponse, ErrorResponse
from app.services.projects import project_service

from app.api.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Crear nuevo proyecto (RF06)

    Acceso: Solo managers

    Validaciones:
    - Fecha fin posterior a fecha inicio
    - Presupuesto mayor a 0
    - Solo gerentes pueden crear proyectos
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden crear proyectos"
        )

    return await project_service.create_project(project_data, created_by=current_user.id)

@router.get("/", response_model=ProjectListResponse)
async def get_projects(
    current_user: UserResponse = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filtrar por estado"),
    search: Optional[str] = Query(None, description="Buscar por nombre")
):
    """
    Obtener lista de proyectos

    Acceso por rol:
    - Manager: Ve todos los proyectos
    - Employee: Ve solo proyectos asignados (RF08)
    - Sponsor: Ve solo sus proyectos (RF09)
    """
    return await project_service.get_projects(
        user_id=current_user.id,
        role=current_user.role,
        page=page,
        limit=limit,
        status_filter=status_filter,
        search=search
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener proyecto especifico

    Validaciones de acceso:
    - Manager: Ve cualquier proyecto
    - Employee: Solo proyectos asignados
    - Sponsor: Solo sus proyectos
    """
    project = await project_service.get_project_by_id(
        project_id=project_id,
        user_id=current_user.id,
        role=current_user.role
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado o sin acceso"
        )

    return project

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Actualizar proyecto

    Acceso: Solo managers
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden actualizar proyectos"
        )

    project = await project_service.update_project(project_id, project_data, user_id=current_user.id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado o sin permisos"
        )

    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Eliminar proyecto

    Acceso: Solo managers
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden eliminar proyectos"
        )

    success = await project_service.delete_project(project_id, user_id=current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado o sin permisos"
        )

@router.post("/{project_id}/employees", response_model=dict)
async def assign_employee_to_project(
    project_id: int,
    assignment: ProjectEmployeeAssign,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Asignar empleado a proyecto (RF07)

    Acceso: Solo managers
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden asignar empleados"
        )

    success = await project_service.assign_employee(
        project_id=project_id,
        employee_id=assignment.employee_id,
        dedication_percentage=assignment.dedication_percentage
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al asignar empleado al proyecto"
        )

    return {"message": "Empleado asignado correctamente"}

@router.delete("/{project_id}/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_employee_from_project(
    project_id: int,
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Remover empleado de proyecto

    Acceso: Solo managers
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden remover empleados"
        )

    success = await project_service.remove_employee(project_id, employee_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignacion no encontrada"
        )

@router.get("/{project_id}/employees", response_model=list)
async def get_project_employees(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """Listar empleados asignados a un proyecto."""
    employees = await project_service.get_project_employees(project_id)
    if employees is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    return employees

@router.put("/{project_id}/employees/{employee_id}", response_model=dict)
async def update_employee_dedication(
    project_id: int,
    employee_id: int,
    assignment: ProjectEmployeeAssign,
    current_user: UserResponse = Depends(get_current_user),
):
    """Actualizar porcentaje de dedicación de un empleado en el proyecto."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden modificar asignaciones",
        )
    success = await project_service.update_employee_dedication(
        project_id, employee_id, float(assignment.dedication_percentage)
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada",
        )
    return {"message": "Dedicación actualizada correctamente"}

@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
async def get_project_stats(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener estadisticas del proyecto (RF13, RF09)

    Acceso:
    - Manager: Estadisticas completas
    - Sponsor: Estadisticas sin informacion interna
    """
    if current_user.role not in ["manager", "sponsor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a estadisticas del proyecto"
        )

    stats = await project_service.get_project_stats(
        project_id=project_id,
        user_id=current_user.id,
        role=current_user.role
    )

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado o sin acceso"
        )

    return stats