from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.auth import UserResponse
from app.services.okrs import okr_service

from app.api.deps import get_current_user

router = APIRouter(prefix="/okrs", tags=["okrs"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class OkrCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)
    project_id: Optional[int] = None
    target_date: Optional[str] = None
    status: Optional[str] = Field(default="active")

class OkrUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    project_id: Optional[int] = None
    target_date: Optional[str] = None
    status: Optional[str] = None

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[dict])
async def get_okrs(
    current_user: UserResponse = Depends(get_current_user),
    project_id: Optional[int] = Query(None),
    okr_status: Optional[str] = Query(None, alias="status"),
):
    """
    Listar OKRs. Acceso: cualquier usuario autenticado.
    Opcionalmente filtrar por proyecto o estado.
    """
    return await okr_service.get_okrs(project_id=project_id, status=okr_status)

@router.get("/{okr_id}", response_model=dict)
async def get_okr(
    okr_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """Obtener un OKR por ID."""
    okr = await okr_service.get_okr(okr_id)
    if not okr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OKR no encontrado",
        )
    return okr

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_okr(
    okr_data: OkrCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Crear nuevo OKR. Acceso: solo managers.
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden crear OKRs",
        )
    payload = okr_data.model_dump()
    payload["created_by"] = current_user.id
    return await okr_service.create_okr(payload)

@router.put("/{okr_id}", response_model=dict)
async def update_okr(
    okr_id: int,
    okr_data: OkrUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Actualizar OKR existente. Acceso: solo managers.
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden editar OKRs",
        )
    result = await okr_service.update_okr(okr_id, okr_data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OKR no encontrado",
        )
    return result

@router.delete("/{okr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_okr(
    okr_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Eliminar OKR. Acceso: solo managers.
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden eliminar OKRs",
        )
    success = await okr_service.delete_okr(okr_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OKR no encontrado",
        )
