from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.models.auth import UserResponse
from app.services.ratings import ratings_service
from app.database import get_admin_supabase

from app.api.deps import get_current_user

router = APIRouter(tags=["ratings"])

class RatingCreate(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

@router.post("/employees/{employee_id}/ratings", status_code=status.HTTP_201_CREATED)
async def create_rating(
    employee_id: int,
    body: RatingCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Calificar a un empleado con estrellas y comentario.
    Acceso: solo managers.
    """
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los gerentes pueden calificar empleados",
        )
    return await ratings_service.create_rating(
        employee_id=employee_id,
        stars=body.stars,
        comment=body.comment,
        rated_by=current_user.id,
    )

@router.get("/employees/{employee_id}/ratings")
async def get_ratings(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Historial de calificaciones de un empleado.
    Acceso: managers (cualquiera) y sponsors (empleados de sus proyectos).
    """
    if current_user.role not in ("manager", "sponsor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta información",
        )

    if current_user.role == "sponsor":
        sb = get_admin_supabase()
        emp_proj = (
            sb.table("project_employees")
            .select("project_id, projects(sponsor_id)")
            .eq("employee_id", employee_id)
            .execute()
        )
        sponsor_projects = [
            r for r in (emp_proj.data or [])
            if (r.get("projects") or {}).get("sponsor_id") == current_user.id
        ]
        if not sponsor_projects:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes ver empleados de tus proyectos",
            )

    return await ratings_service.get_ratings(employee_id)
