from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from typing import Optional

from app.models.auth import (
    EmployeeCreate,
    EmployeeCreateComplete,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeListResponse,
    UserResponse,
    ErrorResponse
)
from app.services.employees import employee_service
from app.services.storage import get_storage_service
from app.services.notifications import notification_service
from app.database import get_admin_supabase

from app.api.deps import get_current_user

router = APIRouter(prefix="/employees", tags=["employees"])

@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee_complete(
    employee_data: EmployeeCreateComplete,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Crear empleado completo (usuario + perfil)

    Acceso: Solo managers

    Flujo mejorado:
    1. Genera contraseña temporal segura automaticamente (12 caracteres)
    2. Crea usuario en Supabase Auth con email y password temporal
    3. Crea registro en tabla users con rol 'employee' y flag must_change_password=True
    4. Crea perfil completo del empleado
    5. Envia email de bienvenida con credenciales (RF03)

    Validaciones (RF03):
    - Email debe ser institucional (.cue.edu.co o .unihumboldt.edu.co)
    - Identificacion debe ser unica
    - Password temporal auto-generada (segura, 12 caracteres)
    - Se envía correo de bienvenida con credenciales
    - Empleado debe cambiar password en primer login

    Mejoras de seguridad:
    - Manager no proporciona password (se genera automaticamente)
    - Password temporal fuerte con caracteres mixtos
    - Forzar cambio en primer login
    - Auditoria completa del proceso
    """
    return await employee_service.create_employee_complete(employee_data, current_user)

@router.post("/profile-only", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee_profile_only(
    employee_data: EmployeeCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Crear solo perfil de empleado (cuando ya existe el usuario)

    Acceso: Solo managers

    Uso: Para casos donde el usuario ya existe en Supabase Auth
    pero no tiene perfil de empleado creado

    Validaciones:
    - El user_id debe existir y tener rol 'employee'
    - La identificacion debe ser unica
    """
    return await employee_service.create_employee(employee_data, current_user)

@router.get("/", response_model=EmployeeListResponse)
async def get_employees(
    current_user: UserResponse = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Numero de pagina"),
    limit: int = Query(50, ge=1, le=100, description="Elementos por pagina"),
    status_filter: Optional[str] = Query(None, regex="^(active|inactive)$", description="Filtrar por estado")
):
    """
    Obtener lista de empleados con paginacion

    Acceso: Solo managers

    Filtros:
    - status: 'active' o 'inactive'

    Paginacion:
    - page: numero de pagina (1-based)
    - limit: elementos por pagina (1-100)
    """
    return await employee_service.get_employees(current_user, page, limit, status_filter)

@router.get("/me/profile", response_model=EmployeeResponse)
async def get_my_employee_profile(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener mi perfil de empleado

    Acceso: Solo empleados

    Uso: Endpoint conveniente para que los empleados obtengan su propio perfil
    """
    if current_user.role != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint es solo para empleados"
        )

    return await employee_service.get_employee_by_user_id(current_user.id, current_user)

@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener empleado por ID

    Acceso:
    - Managers: pueden ver cualquier empleado
    - Empleados: solo pueden ver su propio perfil
    """
    return await employee_service.get_employee(employee_id, current_user)

@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    employee_data: EmployeeUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Actualizar empleado

    Acceso:
    - Managers: pueden editar cualquier empleado (todos los campos)
    - Empleados: solo pueden editar su propio perfil (campos limitados)

    Campos editables por empleados (RF02):
    - address (direccion de residencia)
    - resume_url (foto de perfil/CV)
    - phone (telefono)

    Campos editables por managers:
    - Todos los campos excepto user_id
    """
    return await employee_service.update_employee(employee_id, employee_data, current_user)

@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Desactivar empleado (soft delete)

    Acceso: Solo managers

    Nota: Los empleados no se eliminan fisicamente, solo se marcan como inactivos
    """
    return await employee_service.delete_employee(employee_id, current_user)

@router.get("/by-user/{user_id}", response_model=EmployeeResponse)
async def get_employee_by_user_id(
    user_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener empleado por user_id

    Acceso:
    - Managers: pueden ver cualquier empleado
    - Empleados: solo pueden ver su propio perfil

    Uso: Util para obtener el perfil de empleado usando el ID de usuario de Supabase Auth
    """
    return await employee_service.get_employee_by_user_id(user_id, current_user)

@router.post("/{employee_id}/resume", status_code=status.HTTP_200_OK)
async def upload_resume(
    employee_id: int,
    file: UploadFile = File(..., description="Archivo PDF de la hoja de vida"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Subir hoja de vida (PDF) para un empleado

    Acceso:
    - Managers: pueden subir hoja de vida para cualquier empleado
    - Empleados: solo pueden subir su propia hoja de vida

    Validaciones:
    - Solo archivos PDF
    - Máximo 10MB
    - Empleado debe existir y estar activo

    El archivo se sube a Supabase Storage en el bucket 'resumes'
    y se actualiza automáticamente el campo resume_url del empleado
    """
    # Verificar permisos
    employee = await employee_service.get_employee(employee_id, current_user)

    # Verificar que solo managers o el propio empleado puedan subir archivos
    if current_user.role != "manager" and employee.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para subir archivos a este empleado"
        )

    # Obtener servicio de storage
    storage_service = get_storage_service()

    try:
        # Subir archivo a Supabase Storage
        file_url = await storage_service.upload_resume(file, employee_id)

        # Actualizar el resume_url del empleado
        from app.models.auth import EmployeeUpdate
        update_data = EmployeeUpdate(resume_url=file_url)
        updated_employee = await employee_service.update_employee(
            employee_id,
            update_data,
            current_user
        )

        # RF05: Notificar a los gerentes sobre la nueva hoja de vida (en background)
        try:
            sb = get_admin_supabase()
            managers_res = sb.table("users").select("id, email").eq("role", "manager").execute()
            for mgr in (managers_res.data or []):
                if mgr.get("email"):
                    await notification_service.send_cv_upload_notification(
                        manager_email=mgr["email"],
                        manager_name="Gerente",
                        employee_name=updated_employee.name,
                        employee_id=employee_id,
                    )
        except Exception as notify_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo enviar notificación de CV: {notify_err}")

        return {
            "message": "Hoja de vida subida exitosamente",
            "file_url": file_url,
            "employee": updated_employee
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar el archivo: {str(e)}"
        )

@router.delete("/{employee_id}/resume", status_code=status.HTTP_200_OK)
async def delete_resume(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Eliminar hoja de vida de un empleado

    Acceso:
    - Managers: pueden eliminar hoja de vida de cualquier empleado
    - Empleados: solo pueden eliminar su propia hoja de vida

    Elimina el archivo de Supabase Storage y actualiza el campo resume_url a null
    """
    # Verificar permisos
    employee = await employee_service.get_employee(employee_id, current_user)

    # Verificar que solo managers o el propio empleado puedan eliminar archivos
    if current_user.role != "manager" and employee.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar archivos de este empleado"
        )

    if not employee.resume_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado no tiene hoja de vida registrada"
        )

    # Obtener servicio de storage
    storage_service = get_storage_service()

    try:
        # Eliminar archivo de Supabase Storage
        deleted = await storage_service.delete_resume(employee.resume_url)

        if deleted:
            # Actualizar el resume_url del empleado a null
            from app.models.auth import EmployeeUpdate
            update_data = EmployeeUpdate(resume_url=None)
            updated_employee = await employee_service.update_employee(
                employee_id,
                update_data,
                current_user
            )

            return {
                "message": "Hoja de vida eliminada exitosamente",
                "employee": updated_employee
            }
        else:
            # Si no se pudo eliminar el archivo, al menos limpiar la referencia
            from app.models.auth import EmployeeUpdate
            update_data = EmployeeUpdate(resume_url=None)
            updated_employee = await employee_service.update_employee(
                employee_id,
                update_data,
                current_user
            )

            return {
                "message": "Referencia de hoja de vida eliminada (archivo no encontrado)",
                "employee": updated_employee
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al eliminar el archivo: {str(e)}"
        )