from datetime import datetime
from typing import Optional, List
import logging
from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase, get_admin_supabase
from app.models.auth import (
    EmployeeCreate,
    EmployeeCreateComplete,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeListResponse,
    UserResponse,
    UserRole
)
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

class EmployeeService:
    def __init__(self):
        pass

    async def create_employee_complete(self, employee_data: EmployeeCreateComplete, current_user: UserResponse) -> EmployeeResponse:
        """Crear empleado completo (usuario + perfil) - Solo managers"""
        if current_user.role != UserRole.MANAGER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los managers pueden crear empleados"
            )

        try:
            logger.info(f"🚀 INICIANDO creación de empleado: {employee_data.email}")

            # 1. Generar contraseña temporal segura
            logger.info("📍 Paso 1: Generando contraseña temporal...")
            temporary_password = notification_service.generate_temporary_password()
            logger.info(f"✅ Paso 1 completado - Contraseña generada para {employee_data.email}")

            # 2. Crear usuario en Supabase Auth usando cliente administrativo
            logger.info("📍 Paso 2: Obteniendo cliente administrativo...")
            try:
                # Obtener cliente administrativo con service_role_key
                admin_supabase = get_admin_supabase()
                logger.info("✅ Cliente administrativo obtenido exitosamente")

                logger.info(f"📍 Paso 2b: Creando usuario en Supabase Auth para: {employee_data.email}")

                # Crear usuario sin email de confirmación automático
                auth_response = admin_supabase.auth.admin.create_user({
                    "email": employee_data.email,
                    "password": temporary_password,
                    "email_confirm": True,
                    "user_metadata": {
                        "role": "employee",
                        "created_by": "manager",
                        "must_change_password": True
                    }
                })

                if not auth_response.user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Error al crear usuario en Supabase Auth"
                    )

                logger.info(f"✅ Paso 2 completado - Usuario creado con cliente administrativo: {auth_response.user.id}")

            except Exception as admin_error:
                logger.error(f"Error con cliente administrativo: {admin_error}")
                logger.info("Intentando con método normal como fallback...")

                # Fallback al método normal si el administrativo falla
                auth_response = supabase.auth.sign_up({
                    "email": employee_data.email,
                    "password": temporary_password,
                })

                if not auth_response.user:
                    logger.error(f"❌ Error en fallback también: {admin_error}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Error al crear usuario en Supabase Auth: {str(admin_error)}"
                    )

                logger.info(f"✅ Paso 2c completado - Usuario creado con método fallback: {auth_response.user.id}")
                logger.warning("⚠️ Se envió email de confirmación estándar. Para evitarlo, configura SUPABASE_SERVICE_ROLE_KEY")

            user_id = auth_response.user.id
            logger.info(f"📍 User ID obtenido: {user_id}")

            try:
                # 3. Crear registro en tabla users con rol 'employee' y flag de cambio de password
                logger.info("📍 Paso 3: Creando registro en tabla users...")
                user_insert = admin_supabase.table("users").insert({
                    "id": user_id,
                    "email": employee_data.email,
                    "role": "employee",
                    # "must_change_password": True,  # Columna no existe - comentada temporalmente
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).execute()

                if not user_insert.data:
                    # Si falla, eliminar el usuario de Auth usando cliente administrativo
                    try:
                        admin_supabase = get_admin_supabase()
                        admin_supabase.auth.admin.delete_user(user_id)
                    except:
                        logger.warning("⚠️ No se pudo eliminar usuario de Auth en rollback")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error al crear registro de usuario"
                    )

                logger.info("✅ Paso 3 completado - Registro en tabla users creado")

                # 4. Crear perfil de empleado
                logger.info("📍 Paso 4: Creando perfil en tabla employees...")
                employee_insert = admin_supabase.table("employees").insert({
                    "user_id": user_id,
                    "name": employee_data.name,
                    "identification": employee_data.identification,
                    "position": employee_data.position,
                    "phone": employee_data.phone,
                    "address": employee_data.address,
                    "salary_type": employee_data.salary_type,
                    "salary_hourly": employee_data.salary_hourly,
                    "salary_biweekly": employee_data.salary_biweekly,
                    "salary_monthly": employee_data.salary_monthly,
                    "resume_url": employee_data.resume_url,
                    "status": employee_data.status,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).execute()

                if not employee_insert.data:
                    # Si falla, limpiar usuario creado
                    supabase.table("users").delete().eq("id", user_id).execute()
                    supabase.auth.admin.delete_user(user_id)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error al crear perfil de empleado"
                    )

                employee = employee_insert.data[0]
                logger.info("✅ Paso 4 completado - Perfil de empleado creado")

                # 5. Enviar email de bienvenida personalizado usando SMTP directo (RF03)
                logger.info("📍 Paso 5: Enviando email de bienvenida...")
                try:
                    logger.info(f"🎯 INTENTANDO ENVIAR EMAIL PERSONALIZADO a {employee_data.email}")

                    email_sent = await notification_service.send_employee_welcome_email(
                        email=employee_data.email,
                        name=employee_data.name,
                        temporary_password=temporary_password
                    )

                    if email_sent:
                        logger.info(f"✅ Paso 5 completado - Email enviado exitosamente a {employee_data.email}")
                    else:
                        logger.warning(f"⚠️ Paso 5 falló - Email no se pudo enviar, pero empleado creado exitosamente")

                except Exception as email_error:
                    # No falla la creación si el email falla
                    logger.warning(f"⚠️ Error en Paso 5: {email_error}")
                    logger.error(f"Error enviando email: {email_error}")

                logger.info("🏁 EMPLEADO CREADO EXITOSAMENTE - Construyendo respuesta...")
                return self._build_employee_response(employee)

            except APIError as e:
                logger.error(f"❌ APIError en creación de empleado: {e}")
                logger.error(f"Error en API: {e}")

                # Limpiar en caso de error usando cliente administrativo
                try:
                    admin_supabase = get_admin_supabase()
                    admin_supabase.auth.admin.delete_user(user_id)
                    logger.info("🧹 Usuario eliminado de Auth en rollback")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ No se pudo eliminar usuario de Auth en rollback: {cleanup_error}")

                if "duplicate key value" in str(e).lower():
                    if "identification" in str(e).lower():
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La identificación ya está registrada"
                        )
                    elif "email" in str(e).lower():
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El email ya está registrado"
                        )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error API al crear empleado: {str(e)}"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al crear empleado completo: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")

            # Intentar obtener más información del error
            if hasattr(e, 'details'):
                logger.error(f"Detalles adicionales: {e.details}")
            if hasattr(e, 'message'):
                logger.error(f"Mensaje del error: {e.message}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    async def create_employee(self, employee_data: EmployeeCreate, current_user: UserResponse) -> EmployeeResponse:
        """Crear empleado (solo managers)"""
        if current_user.role != UserRole.MANAGER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los managers pueden crear empleados"
            )

        try:
            # Verificar que el user_id existe y tiene rol employee
            user_query = supabase.table("users").select("*").eq("id", employee_data.user_id).execute()
            if not user_query.data or user_query.data[0]["role"] != "employee":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario debe tener rol de empleado"
                )

            # Verificar que no existe ya un empleado con esta user_id
            existing_employee = supabase.table("employees").select("id").eq("user_id", employee_data.user_id).execute()
            if existing_employee.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe un perfil de empleado para este usuario"
                )

            # Insertar empleado
            employee_insert = supabase.table("employees").insert({
                "user_id": employee_data.user_id,
                "name": employee_data.name,
                "identification": employee_data.identification,
                "position": employee_data.position,
                "phone": employee_data.phone,
                "address": employee_data.address,
                "salary_type": employee_data.salary_type,
                "salary_hourly": employee_data.salary_hourly,
                "salary_biweekly": employee_data.salary_biweekly,
                "salary_monthly": employee_data.salary_monthly,
                "resume_url": employee_data.resume_url,
                "status": employee_data.status,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()

            if not employee_insert.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al crear empleado"
                )

            employee = employee_insert.data[0]
            return self._build_employee_response(employee)

        except HTTPException:
            raise
        except APIError as e:
            if "duplicate key value" in str(e).lower() and "identification" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La identificación ya está registrada"
                )
            logger.error(f"API Error al crear empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear empleado"
            )
        except Exception as e:
            logger.error(f"Error al crear empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def get_employee(self, employee_id: int, current_user: UserResponse) -> EmployeeResponse:
        """Obtener empleado por ID"""
        try:
            admin_client = get_admin_supabase()
            query = admin_client.table("employees").select("*").eq("id", employee_id)

            # Si no es manager, solo puede ver su propio perfil
            if current_user.role != UserRole.MANAGER:
                query = query.eq("user_id", current_user.id)

            employee_query = query.execute()

            if not employee_query.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Empleado no encontrado"
                )

            employee = employee_query.data[0]
            return self._build_employee_response(employee)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al obtener empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def get_employees(self, current_user: UserResponse, page: int = 1, limit: int = 50, status_filter: Optional[str] = None) -> EmployeeListResponse:
        """Obtener lista de empleados (solo managers)"""
        if current_user.role != UserRole.MANAGER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los managers pueden listar todos los empleados"
            )

        try:
            # Usar cliente administrativo para evitar problemas de RLS
            admin_client = get_admin_supabase()

            # Query base
            query = admin_client.table("employees").select("*")

            # Filtrar por status si se especifica
            if status_filter:
                query = query.eq("status", status_filter)

            # Ordenar por fecha de creación (más recientes primero)
            query = query.order("created_at", desc=True)

            # Paginación
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1)

            employees_query = query.execute()

            # Contar total de empleados usando el cliente administrativo
            count_query = admin_client.table("employees").select("id", count="exact")
            if status_filter:
                count_query = count_query.eq("status", status_filter)
            count_result = count_query.execute()
            total = count_result.count if count_result.count is not None else 0

            employees = [self._build_employee_response(emp) for emp in employees_query.data]

            return EmployeeListResponse(
                employees=employees,
                total=total,
                page=page,
                limit=limit
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al obtener empleados: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def update_employee(self, employee_id: int, employee_data: EmployeeUpdate, current_user: UserResponse) -> EmployeeResponse:
        """Actualizar empleado"""
        try:
            # Verificar que el empleado existe
            existing_query = supabase.table("employees").select("*").eq("id", employee_id).execute()
            if not existing_query.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Empleado no encontrado"
                )

            existing_employee = existing_query.data[0]

            # Control de acceso: managers pueden editar cualquier empleado, empleados solo su perfil
            if current_user.role != UserRole.MANAGER and current_user.id != existing_employee["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para editar este empleado"
                )

            # Si es empleado, restringir campos que puede editar (según RF02)
            update_data = {}
            if current_user.role == UserRole.EMPLOYEE:
                # Empleados solo pueden editar: foto de perfil, correo (en users), dirección
                if employee_data.address is not None:
                    update_data["address"] = employee_data.address
                if employee_data.resume_url is not None:
                    update_data["resume_url"] = employee_data.resume_url
                if employee_data.phone is not None:
                    update_data["phone"] = employee_data.phone
            else:
                # Managers pueden editar todos los campos
                for field, value in employee_data.model_dump(exclude_unset=True).items():
                    if value is not None:
                        update_data[field] = value

            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No hay campos para actualizar"
                )

            update_data["updated_at"] = datetime.utcnow().isoformat()

            # Actualizar empleado
            employee_update = supabase.table("employees").update(update_data).eq("id", employee_id).execute()

            if not employee_update.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al actualizar empleado"
                )

            employee = employee_update.data[0]
            return self._build_employee_response(employee)

        except HTTPException:
            raise
        except APIError as e:
            if "duplicate key value" in str(e).lower() and "identification" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La identificación ya está registrada"
                )
            logger.error(f"API Error al actualizar empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar empleado"
            )
        except Exception as e:
            logger.error(f"Error al actualizar empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def delete_employee(self, employee_id: int, current_user: UserResponse) -> dict:
        """Eliminar empleado (solo managers)"""
        if current_user.role != UserRole.MANAGER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los managers pueden eliminar empleados"
            )

        try:
            # Verificar que el empleado existe
            existing_query = supabase.table("employees").select("*").eq("id", employee_id).execute()
            if not existing_query.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Empleado no encontrado"
                )

            # En lugar de eliminar físicamente, marcamos como inactivo (soft delete)
            employee_update = supabase.table("employees").update({
                "status": "inactive",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", employee_id).execute()

            if not employee_update.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al desactivar empleado"
                )

            return {"message": "Empleado desactivado exitosamente", "employee_id": employee_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al desactivar empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def get_employee_by_user_id(self, user_id: str, current_user: UserResponse) -> EmployeeResponse:
        """Obtener empleado por user_id"""
        try:
            # Control de acceso
            if current_user.role != UserRole.MANAGER and current_user.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver este empleado"
                )

            employee_query = supabase.table("employees").select("*").eq("user_id", user_id).execute()

            if not employee_query.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Empleado no encontrado"
                )

            employee = employee_query.data[0]
            return self._build_employee_response(employee)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al obtener empleado por user_id: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    def _build_employee_response(self, employee_data: dict) -> EmployeeResponse:
        """Construir respuesta de empleado desde datos de BD"""
        return EmployeeResponse(
            id=employee_data["id"],
            user_id=employee_data["user_id"],
            name=employee_data["name"],
            identification=employee_data["identification"],
            position=employee_data["position"],
            phone=employee_data["phone"],
            address=employee_data["address"],
            salary_type=employee_data["salary_type"],
            salary_hourly=employee_data["salary_hourly"],
            salary_biweekly=employee_data["salary_biweekly"],
            salary_monthly=employee_data["salary_monthly"],
            resume_url=employee_data["resume_url"],
            status=employee_data["status"],
            created_at=datetime.fromisoformat(employee_data["created_at"].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(employee_data["updated_at"].replace('Z', '+00:00')) if employee_data["updated_at"] else None
        )

# Instancia global del servicio
employee_service = EmployeeService()