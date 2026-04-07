from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.database import supabase, get_admin_supabase
from app.models.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectEmployeeResponse,
    ProjectStatsResponse
)
from app.services.notifications import notification_service
from app.services.email import email_service

logger = logging.getLogger(__name__)

class ProjectService:
    async def create_project(self, project_data: ProjectCreate, created_by: str) -> ProjectResponse:
        """Crear nuevo proyecto con código único generado"""
        try:
            # Insertar proyecto en la base de datos
            project_dict = project_data.model_dump()

            # Registrar el gerente que crea el proyecto
            project_dict['created_by'] = created_by

            # Convertir budget a float si existe
            if project_dict.get('budget'):
                project_dict['budget'] = float(project_dict['budget'])

            # Convertir fechas a strings para JSON serialization
            if project_dict.get('start_date'):
                project_dict['start_date'] = project_dict['start_date'].isoformat()
            if project_dict.get('end_date'):
                project_dict['end_date'] = project_dict['end_date'].isoformat()

            # Filtrar campos None/vacíos para evitar enviarlos a la base de datos
            project_dict = {k: v for k, v in project_dict.items() if v is not None}

            response = supabase.table("projects").insert(project_dict).execute()

            if response.data:
                project = response.data[0]
                logger.info(f"Proyecto creado: ID {project['id']}")

                # Si hay sponsor asignado, crear notificación
                if project.get('sponsor_id'):
                    await self._notify_sponsor_assignment(project['id'], project['sponsor_id'])

                return await self._format_project_response(project)

            raise Exception("Error al crear proyecto")

        except Exception as e:
            logger.error(f"Error creando proyecto: {e}")
            raise

    async def get_projects(
        self,
        user_id: str,
        role: str,
        page: int = 1,
        limit: int = 10,
        status_filter: Optional[str] = None,
        search: Optional[str] = None
    ) -> ProjectListResponse:
        """Obtener lista de proyectos según rol del usuario"""
        try:
            offset = (page - 1) * limit

            project_ids = None
            if role == "employee":
                employee_id = await self._get_employee_id_by_user(user_id)
                if employee_id is None:
                    return ProjectListResponse(projects=[], total=0, page=page, limit=limit)
                pe_response = supabase.table("project_employees").select("project_id").eq("employee_id", employee_id).execute()
                project_ids = [row["project_id"] for row in pe_response.data] if pe_response.data else []

            select_str = """
                *,
                users!projects_sponsor_id_fkey(email),
                project_employees(
                    id,
                    employee_id,
                    dedication_percentage,
                    assigned_at,
                    employees(
                        id,
                        name,
                        position
                    )
                )
            """
            admin = get_admin_supabase()
            query = admin.table("projects").select(select_str)
            count_query = admin.table("projects").select("id", count="exact")

            # Filtros según rol
            if role == "manager":
                query = query.eq("created_by", user_id)
                count_query = count_query.eq("created_by", user_id)
            elif role == "employee":
                if project_ids:
                    query = query.in_("id", project_ids)
                    count_query = count_query.in_("id", project_ids)
                else:
                    # No projects assigned → return empty immediately
                    return ProjectListResponse(projects=[], total=0, page=page, limit=limit)
            elif role == "sponsor":
                query = query.eq("sponsor_id", user_id)
                count_query = count_query.eq("sponsor_id", user_id)

            # Filtros adicionales
            if status_filter:
                query = query.eq("status", status_filter)
                count_query = count_query.eq("status", status_filter)

            if search:
                query = query.ilike("name", f"%{search}%")
                count_query = count_query.ilike("name", f"%{search}%")

            # Paginación
            response = query.range(offset, offset + limit - 1).execute()
            count_response = count_query.execute()

            projects = []
            for project in response.data:
                projects.append(await self._format_project_response(project))

            return ProjectListResponse(
                projects=projects,
                total=count_response.count or 0,
                page=page,
                limit=limit
            )

        except Exception as e:
            logger.error(f"Error obteniendo proyectos: {e}")
            raise

    async def get_project_by_id(
        self,
        project_id: int,
        user_id: str,
        role: str
    ) -> Optional[ProjectResponse]:
        """Obtener proyecto por ID con validaciones de acceso"""
        try:
            query = get_admin_supabase().table("projects").select("""
                *,
                users!projects_sponsor_id_fkey(email),
                project_employees(
                    id,
                    employee_id,
                    dedication_percentage,
                    assigned_at,
                    employees(
                        id,
                        name,
                        position
                    )
                )
            """).eq("id", project_id)

            response = query.execute()

            if not response.data:
                return None

            project = response.data[0]

            # Validar acceso según rol
            if role == "manager":
                if project.get('created_by') != user_id:
                    return None
            elif role == "employee":
                employee_id = await self._get_employee_id_by_user(user_id)
                assigned_employees = [pe['employee_id'] for pe in project.get('project_employees', [])]
                if employee_id not in assigned_employees:
                    return None
            elif role == "sponsor":
                if project.get('sponsor_id') != user_id:
                    return None

            return await self._format_project_response(project)

        except Exception as e:
            logger.error(f"Error obteniendo proyecto {project_id}: {e}")
            return None

    async def update_project(
        self,
        project_id: int,
        project_data: ProjectUpdate,
        user_id: str
    ) -> Optional[ProjectResponse]:
        """Actualizar proyecto"""
        try:
            # Verificar que el gerente es el creador del proyecto
            check = get_admin_supabase().table("projects").select("created_by").eq("id", project_id).execute()
            if not check.data or check.data[0].get("created_by") != user_id:
                return None

            update_dict = project_data.model_dump(exclude_unset=True)

            # Convertir budget a float si existe
            if 'budget' in update_dict and update_dict['budget']:
                update_dict['budget'] = float(update_dict['budget'])

            # Convertir fechas a strings para JSON serialization
            if 'start_date' in update_dict and update_dict['start_date']:
                update_dict['start_date'] = update_dict['start_date'].isoformat()
            if 'end_date' in update_dict and update_dict['end_date']:
                update_dict['end_date'] = update_dict['end_date'].isoformat()

            # Filtrar campos None/vacíos para evitar enviarlos a la base de datos
            update_dict = {k: v for k, v in update_dict.items() if v is not None}

            update_dict['updated_at'] = datetime.now().isoformat()

            response = supabase.table("projects").update(update_dict).eq("id", project_id).execute()

            if response.data:
                project = response.data[0]
                logger.info(f"Proyecto actualizado: ID {project_id}")
                return await self._format_project_response(project)

            return None

        except Exception as e:
            logger.error(f"Error actualizando proyecto {project_id}: {e}")
            return None

    async def delete_project(self, project_id: int, user_id: str) -> bool:
        """Eliminar proyecto"""
        try:
            # Verificar que el gerente es el creador del proyecto
            check = get_admin_supabase().table("projects").select("created_by").eq("id", project_id).execute()
            if not check.data or check.data[0].get("created_by") != user_id:
                return False

            response = supabase.table("projects").delete().eq("id", project_id).execute()
            success = len(response.data) > 0

            if success:
                logger.info(f"Proyecto eliminado: ID {project_id}")

            return success

        except Exception as e:
            logger.error(f"Error eliminando proyecto {project_id}: {e}")
            return False

    async def assign_employee(
        self,
        project_id: int,
        employee_id: int,
        dedication_percentage: float
    ) -> bool:
        """Asignar empleado a proyecto"""
        try:
            admin = get_admin_supabase()
            ded = float(dedication_percentage)

            # Verificar si ya está asignado
            existing = admin.table("project_employees").select("id").eq("project_id", project_id).eq("employee_id", employee_id).execute()
            if existing.data:
                # Actualizar porcentaje de dedicación si ya existe
                admin.table("project_employees").update({
                    "dedication_percentage": ded
                }).eq("project_id", project_id).eq("employee_id", employee_id).execute()
            else:
                # Crear nueva asignación
                admin.table("project_employees").insert({
                    "project_id": project_id,
                    "employee_id": employee_id,
                    "dedication_percentage": ded
                }).execute()

            # Crear notificación para el empleado
            await self._notify_employee_assignment(project_id, employee_id)
            logger.info(f"Empleado {employee_id} asignado al proyecto {project_id}")
            return True

        except Exception as e:
            logger.error(f"Error asignando empleado {employee_id} al proyecto {project_id}: {e}")
            return False

    async def get_project_employees(
        self, project_id: int
    ) -> Optional[List[ProjectEmployeeResponse]]:
        """Listar empleados asignados a un proyecto"""
        try:
            check = supabase.table("projects").select("id").eq("id", project_id).execute()
            if not check.data:
                return None

            response = (
                supabase.table("project_employees")
                .select("id, employee_id, dedication_percentage, assigned_at, employees(id, name, position)")
                .eq("project_id", project_id)
                .execute()
            )

            result = []
            for pe in response.data:
                employee = pe.get("employees") or {}
                result.append(ProjectEmployeeResponse(
                    id=pe["id"],
                    employee_id=pe["employee_id"],
                    employee_name=employee.get("name", ""),
                    employee_position=employee.get("position"),
                    dedication_percentage=pe["dedication_percentage"],
                    assigned_at=datetime.fromisoformat(pe["assigned_at"]),
                ))
            return result

        except Exception as e:
            logger.error(f"Error obteniendo empleados del proyecto {project_id}: {e}")
            return None

    async def update_employee_dedication(
        self, project_id: int, employee_id: int, dedication_percentage: float
    ) -> bool:
        """Actualizar porcentaje de dedicación de un empleado en el proyecto"""
        try:
            get_admin_supabase().table("project_employees").update({
                "dedication_percentage": float(dedication_percentage)
            }).eq("project_id", project_id).eq("employee_id", employee_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error actualizando dedicación: {e}")
            return False

    async def remove_employee(self, project_id: int, employee_id: int) -> bool:
        """Remover empleado de proyecto"""
        try:
            response = get_admin_supabase().table("project_employees").delete().eq("project_id", project_id).eq("employee_id", employee_id).execute()
            success = len(response.data) > 0

            if success:
                logger.info(f"Empleado {employee_id} removido del proyecto {project_id}")

            return success

        except Exception as e:
            logger.error(f"Error removiendo empleado {employee_id} del proyecto {project_id}: {e}")
            return False

    async def get_project_stats(
        self,
        project_id: int,
        user_id: str,
        role: str
    ) -> Optional[ProjectStatsResponse]:
        """Obtener estadísticas del proyecto"""
        try:
            # Validar acceso al proyecto
            project = await self.get_project_by_id(project_id, user_id, role)
            if not project:
                return None

            # Estadísticas básicas del proyecto
            stats = {
                "total_projects": 1,
                "active_projects": 1 if project.status == "active" else 0,
                "completed_projects": 1 if project.status == "completed" else 0,
                "total_budget": project.budget or 0,
                "spent_budget": 0,  # Se calculará con las transacciones
                "employees_assigned": len(project.assigned_employees)
            }

            # Si es manager, incluir información financiera detallada
            if role == "manager":
                # Calcular gastos del proyecto
                expenses_response = supabase.table("transactions").select("amount").eq("project_id", project_id).eq("type", "expense").execute()
                if expenses_response.data:
                    stats["spent_budget"] = sum(float(expense["amount"]) for expense in expenses_response.data)

            return ProjectStatsResponse(**stats)

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del proyecto {project_id}: {e}")
            return None

    async def _format_project_response(self, project_data: Dict[str, Any]) -> ProjectResponse:
        """Formatear respuesta del proyecto con empleados asignados"""
        assigned_employees = []

        if project_data.get('project_employees'):
            for pe in project_data['project_employees']:
                if pe.get('employees'):
                    employee = pe['employees']
                    assigned_employees.append(ProjectEmployeeResponse(
                        id=pe['id'],
                        employee_id=pe['employee_id'],
                        employee_name=employee['name'],
                        employee_position=employee.get('position'),
                        dedication_percentage=pe['dedication_percentage'],
                        assigned_at=datetime.fromisoformat(pe['assigned_at'])
                    ))

        sponsor_email = None
        if project_data.get('users'):
            sponsor_email = project_data['users']['email']

        # RF06: código único de proyecto (determinístico desde id + año)
        created_year = datetime.fromisoformat(project_data['created_at']).year
        project_code = f"PROY-{created_year}-{project_data['id']:04d}"

        return ProjectResponse(
            id=project_data['id'],
            code=project_code,
            name=project_data['name'],
            description=project_data.get('description'),
            start_date=project_data['start_date'],
            end_date=project_data.get('end_date'),
            budget=project_data.get('budget'),
            status=project_data['status'],
            sponsor_id=project_data.get('sponsor_id'),
            sponsor_email=sponsor_email,
            created_at=datetime.fromisoformat(project_data['created_at']),
            updated_at=datetime.fromisoformat(project_data['updated_at']) if project_data.get('updated_at') else None,
            assigned_employees=assigned_employees
        )

    async def _get_employee_id_by_user(self, user_id: str) -> Optional[int]:
        """Obtener ID del empleado por user_id"""
        try:
            response = supabase.table("employees").select("id").eq("user_id", user_id).execute()
            return response.data[0]['id'] if response.data else None
        except Exception as e:
            logger.error(f"Error obteniendo employee_id para user {user_id}: {e}")
            return None

    async def _notify_employee_assignment(self, project_id: int, employee_id: int):
        """Crear notificación de asignación a proyecto"""
        try:
            # Obtener información del empleado
            employee_response = supabase.table("employees").select("user_id, name").eq("id", employee_id).execute()
            if not employee_response.data:
                return

            employee = employee_response.data[0]

            # Obtener información del proyecto
            project_response = supabase.table("projects").select("name").eq("id", project_id).execute()
            if not project_response.data:
                return

            project_name = project_response.data[0]['name']

            # Crear notificación
            await notification_service.create_notification(
                user_id=employee['user_id'],
                title="Asignación a proyecto",
                message=f"Has sido asignado al proyecto: {project_name}",
                type="info",
                related_table="projects",
                related_id=project_id
            )

            # Enviar email de notificación
            await email_service.send_project_assignment_notification(
                employee['user_id'],
                project_name
            )

        except Exception as e:
            logger.error(f"Error enviando notificación de asignación: {e}")

    async def _notify_sponsor_assignment(self, project_id: int, sponsor_id: str):
        """Crear notificación para sponsor sobre nuevo proyecto"""
        try:
            project_response = supabase.table("projects").select("name").eq("id", project_id).execute()
            if not project_response.data:
                return

            project_name = project_response.data[0]['name']

            await notification_service.create_notification(
                user_id=sponsor_id,
                title="Proyecto asignado",
                message=f"Has sido asignado como patrocinador del proyecto: {project_name}",
                type="info",
                related_table="projects",
                related_id=project_id
            )

        except Exception as e:
            logger.error(f"Error notificando sponsor: {e}")

project_service = ProjectService()