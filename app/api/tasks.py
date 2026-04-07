from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from typing import Optional, List

from app.models.task import (
    TaskCreate,
    TaskUpdate,
    TaskStatusUpdate,
    TaskResponse,
    TaskStatusResponse,
    TaskDeliverableResponse,
    TaskListResponse,
)
from app.models.auth import UserResponse
from app.services.tasks import task_service

from app.api.deps import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ---------------------------------------------------------------------------
# CRUD de Tareas
# ---------------------------------------------------------------------------

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Crear nueva tarea. Acceso: managers."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden crear tareas",
        )
    return await task_service.create_task(task_data)

@router.get("/", response_model=TaskListResponse)
async def get_tasks(
    current_user: UserResponse = Depends(get_current_user),
    project_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    task_status: Optional[str] = Query(None, alias="status"),
):
    """
    Listar tareas con filtros opcionales.
    - Manager: ve todas las tareas (filtros opcionales)
    - Employee: ve solo sus tareas
    """
    return await task_service.get_tasks(
        user_id=current_user.id,
        role=current_user.role,
        project_id=project_id,
        employee_id=employee_id,
        status=task_status,
    )

@router.get("/deliverables", response_model=List[dict])
async def get_all_deliverables(
    current_user: UserResponse = Depends(get_current_user),
):
    """Listar todos los entregables con info de tarea/proyecto/empleado. Solo managers."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden ver todos los entregables",
        )
    return await task_service.get_all_deliverables()

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """Obtener tarea por ID con sus entregables."""
    task = await task_service.get_task_by_id(task_id, current_user.id, current_user.role)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada o sin acceso",
        )
    return task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Actualizar tarea. Acceso: managers."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden editar tareas",
        )
    task = await task_service.update_task(task_id, task_data, current_user.id, current_user.role)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada",
        )
    return task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """Eliminar tarea. Acceso: managers."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden eliminar tareas",
        )
    success = await task_service.delete_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada",
        )

# ---------------------------------------------------------------------------
# Cambio de estado (Kanban drag & drop)
# ---------------------------------------------------------------------------

@router.patch("/{task_id}/status", response_model=TaskStatusResponse)
async def update_task_status(
    task_id: int,
    status_data: TaskStatusUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Cambiar estado de tarea para drag & drop del Kanban.
    Auto-asigna completed_at cuando status = 'completed'.
    Acceso: managers y el empleado asignado.
    """
    result = await task_service.update_task_status(task_id, status_data.status)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada",
        )
    return result

# ---------------------------------------------------------------------------
# Entregables
# ---------------------------------------------------------------------------

@router.post(
    "/{task_id}/deliverables",
    response_model=TaskDeliverableResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_deliverable(
    task_id: int,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
):
    """Subir archivo entregable a una tarea (máx 10MB)."""
    return await task_service.upload_deliverable(task_id, file)

@router.get("/{task_id}/deliverables", response_model=List[TaskDeliverableResponse])
async def get_deliverables(
    task_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """Listar entregables de una tarea."""
    return await task_service.get_deliverables(task_id)

@router.delete(
    "/{task_id}/deliverables/{deliverable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_deliverable(
    task_id: int,
    deliverable_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """Eliminar entregable de una tarea. Acceso: managers."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden eliminar entregables",
        )
    success = await task_service.delete_deliverable(task_id, deliverable_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entregable no encontrado",
        )
