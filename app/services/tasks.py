import uuid
import logging
from typing import Optional, List
from datetime import datetime
from fastapi import UploadFile, HTTPException

from app.database import get_admin_supabase
from app.services.notifications import notification_service

supabase = get_admin_supabase()
from app.models.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskStatusResponse,
    TaskDeliverableResponse,
    TaskListResponse,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
DELIVERABLES_BUCKET = "deliverables"


class TaskService:
    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    async def create_task(self, data: TaskCreate) -> TaskResponse:
        try:
            task_dict = data.model_dump()
            if task_dict.get("due_date"):
                task_dict["due_date"] = task_dict["due_date"].isoformat()

            response = supabase.table("tasks").insert(task_dict).execute()
            if not response.data:
                raise Exception("Error al crear tarea")

            task_row = response.data[0]
            logger.info(f"Tarea creada: ID {task_row['id']}")

            # RF24: Notificar al empleado asignado por correo
            try:
                emp_res = (
                    supabase.table("employees")
                    .select("name, user_id")
                    .eq("id", data.employee_id)
                    .single()
                    .execute()
                )
                if emp_res.data:
                    emp_name = emp_res.data["name"]
                    user_id = emp_res.data["user_id"]
                    user_res = (
                        supabase.table("users")
                        .select("email")
                        .eq("id", user_id)
                        .single()
                        .execute()
                    )
                    if user_res.data and user_res.data.get("email"):
                        # Obtener nombre del proyecto
                        proj_res = (
                            supabase.table("projects")
                            .select("name")
                            .eq("id", data.project_id)
                            .single()
                            .execute()
                        )
                        project_name = proj_res.data["name"] if proj_res.data else ""
                        await notification_service.send_task_assignment_notification(
                            employee_email=user_res.data["email"],
                            employee_name=emp_name,
                            task_title=data.title,
                            task_description=data.description or "",
                            due_date=task_dict.get("due_date", "") or "",
                            priority=data.priority,
                            project_name=project_name,
                        )
            except Exception as notify_err:
                logger.warning(f"No se pudo enviar notificación de tarea: {notify_err}")

            return await self._format_task(task_row)
        except Exception as e:
            logger.error(f"Error creando tarea: {e}")
            raise

    async def get_tasks(
        self,
        user_id: str,
        role: str,
        project_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> TaskListResponse:
        try:
            query = supabase.table("tasks").select(
                "*, projects(id, name), employees(id, name)"
            )

            # Empleados solo ven sus propias tareas
            if role == "employee":
                emp_id = await self._get_employee_id(user_id)
                if emp_id is None:
                    return TaskListResponse(tasks=[], total=0)
                query = query.eq("employee_id", emp_id)
            elif employee_id:
                query = query.eq("employee_id", employee_id)

            if project_id:
                query = query.eq("project_id", project_id)
            if status:
                query = query.eq("status", status)

            response = query.order("created_at", desc=True).execute()

            tasks = []
            for row in response.data:
                tasks.append(await self._format_task(row, include_deliverables=False))

            return TaskListResponse(tasks=tasks, total=len(tasks))
        except Exception as e:
            logger.error(f"Error obteniendo tareas: {e}")
            raise

    async def get_task_by_id(
        self, task_id: int, user_id: str, role: str
    ) -> Optional[TaskResponse]:
        try:
            response = (
                supabase.table("tasks")
                .select("*, projects(id, name), employees(id, name)")
                .eq("id", task_id)
                .execute()
            )
            if not response.data:
                return None

            task = response.data[0]

            # Empleados solo pueden ver sus tareas
            if role == "employee":
                emp_id = await self._get_employee_id(user_id)
                if task.get("employee_id") != emp_id:
                    return None

            return await self._format_task(task, include_deliverables=True)
        except Exception as e:
            logger.error(f"Error obteniendo tarea {task_id}: {e}")
            return None

    async def update_task(
        self, task_id: int, data: TaskUpdate, user_id: str, role: str
    ) -> Optional[TaskResponse]:
        try:
            update_dict = data.model_dump(exclude_unset=True)

            if "due_date" in update_dict and update_dict["due_date"]:
                update_dict["due_date"] = update_dict["due_date"].isoformat()

            # Auto-set completed_at on status change
            if "status" in update_dict:
                if update_dict["status"] == "completed":
                    update_dict["completed_at"] = datetime.now().isoformat()
                else:
                    update_dict["completed_at"] = None

            update_dict["updated_at"] = datetime.now().isoformat()

            response = (
                supabase.table("tasks")
                .update(update_dict)
                .eq("id", task_id)
                .execute()
            )
            if not response.data:
                return None

            logger.info(f"Tarea actualizada: ID {task_id}")
            return await self._format_task(response.data[0])
        except Exception as e:
            logger.error(f"Error actualizando tarea {task_id}: {e}")
            return None

    async def delete_task(self, task_id: int) -> bool:
        try:
            response = supabase.table("tasks").delete().eq("id", task_id).execute()
            success = len(response.data) > 0
            if success:
                logger.info(f"Tarea eliminada: ID {task_id}")
            return success
        except Exception as e:
            logger.error(f"Error eliminando tarea {task_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # CAMBIO DE ESTADO
    # -------------------------------------------------------------------------

    async def update_task_status(
        self, task_id: int, status: str
    ) -> Optional[TaskStatusResponse]:
        try:
            # RF12: al completar, verificar que exista al menos un entregable
            if status == "completed":
                deliverables_check = (
                    supabase.table("task_deliverables")
                    .select("id")
                    .eq("task_id", task_id)
                    .execute()
                )
                if not deliverables_check.data or len(deliverables_check.data) == 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Debes subir al menos un entregable antes de marcar la tarea como completada"
                    )

            update_dict: dict = {
                "status": status,
                "updated_at": datetime.now().isoformat(),
            }

            if status == "completed":
                update_dict["completed_at"] = datetime.now().isoformat()
            else:
                update_dict["completed_at"] = None

            response = (
                supabase.table("tasks")
                .update(update_dict)
                .eq("id", task_id)
                .execute()
            )
            if not response.data:
                return None

            task = response.data[0]
            logger.info(f"Estado de tarea {task_id} cambiado a '{status}'")
            return TaskStatusResponse(
                id=task["id"],
                status=task["status"],
                completed_at=(
                    datetime.fromisoformat(task["completed_at"])
                    if task.get("completed_at")
                    else None
                ),
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error cambiando estado de tarea {task_id}: {e}")
            return None

    # -------------------------------------------------------------------------
    # ENTREGABLES
    # -------------------------------------------------------------------------

    async def upload_deliverable(
        self, task_id: int, file: UploadFile
    ) -> TaskDeliverableResponse:
        # Validar tamaño
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, detail="El archivo no puede exceder 10MB"
            )

        try:
            ext = (file.filename or "file").rsplit(".", 1)[-1]
            path = f"task_{task_id}/{uuid.uuid4()}.{ext}"

            supabase.storage.from_(DELIVERABLES_BUCKET).upload(
                file=content,
                path=path,
                file_options={"content-type": file.content_type or "application/octet-stream"},
            )

            public_url = supabase.storage.from_(DELIVERABLES_BUCKET).get_public_url(path)

            record = {
                "task_id": task_id,
                "file_url": public_url,
                "file_name": file.filename or path,
                "file_type": file.content_type or "application/octet-stream",
                "file_size": len(content),
            }
            result = supabase.table("task_deliverables").insert(record).execute()
            if not result.data:
                raise Exception("Error al guardar metadata del entregable")

            row = result.data[0]
            logger.info(f"Entregable subido para tarea {task_id}: {file.filename}")
            return TaskDeliverableResponse(
                id=row["id"],
                task_id=row["task_id"],
                file_name=row["file_name"],
                file_url=row["file_url"],
                file_size=row["file_size"],
                uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error subiendo entregable para tarea {task_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

    async def get_all_deliverables(self, manager_id: str) -> List[dict]:
        """Obtener entregables del gerente actual (solo proyectos que él creó)."""
        try:
            # 1. Obtener los IDs de proyectos del gerente
            proj_resp = (
                supabase.table("projects")
                .select("id")
                .eq("created_by", manager_id)
                .execute()
            )
            project_ids = [p["id"] for p in proj_resp.data]
            if not project_ids:
                return []

            # 2. Obtener los IDs de tareas dentro de esos proyectos
            task_resp = (
                supabase.table("tasks")
                .select("id")
                .in_("project_id", project_ids)
                .execute()
            )
            task_ids = [t["id"] for t in task_resp.data]
            if not task_ids:
                return []

            # 3. Obtener entregables solo de esas tareas
            response = (
                supabase.table("task_deliverables")
                .select("*, tasks(id, title, status, projects(id, name), employees(id, name))")
                .in_("task_id", task_ids)
                .order("uploaded_at", desc=True)
                .execute()
            )
            result = []
            for d in response.data:
                task = d.get("tasks") or {}
                project = task.get("projects") or {}
                employee = task.get("employees") or {}
                result.append({
                    "id": d["id"],
                    "task_id": d["task_id"],
                    "task_title": task.get("title", ""),
                    "task_status": task.get("status", ""),
                    "project_name": project.get("name", ""),
                    "employee_name": employee.get("name", ""),
                    "file_name": d["file_name"],
                    "file_url": d["file_url"],
                    "file_size": d.get("file_size") or 0,
                    "uploaded_at": d["uploaded_at"],
                })
            return result
        except Exception as e:
            logger.error(f"Error obteniendo entregables del gerente {manager_id}: {e}")
            raise

    async def get_deliverables(self, task_id: int) -> List[TaskDeliverableResponse]:
        try:
            response = (
                supabase.table("task_deliverables")
                .select("*")
                .eq("task_id", task_id)
                .order("uploaded_at", desc=True)
                .execute()
            )
            return [self._format_deliverable(r) for r in response.data]
        except Exception as e:
            logger.error(f"Error obteniendo entregables de tarea {task_id}: {e}")
            return []

    async def delete_deliverable(self, task_id: int, deliverable_id: int) -> bool:
        try:
            row = (
                supabase.table("task_deliverables")
                .select("file_url")
                .eq("id", deliverable_id)
                .eq("task_id", task_id)
                .execute()
            )
            if not row.data:
                return False

            # Eliminar de Storage
            file_url = row.data[0]["file_url"]
            path = self._extract_storage_path(file_url)
            if path:
                supabase.storage.from_(DELIVERABLES_BUCKET).remove([path])

            # Eliminar de BD
            result = (
                supabase.table("task_deliverables")
                .delete()
                .eq("id", deliverable_id)
                .execute()
            )
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error eliminando entregable {deliverable_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    async def _format_task(
        self, row: dict, include_deliverables: bool = False
    ) -> TaskResponse:
        project_name = ""
        if row.get("projects"):
            project_name = row["projects"]["name"]
        elif row.get("project_id"):
            pr = (
                supabase.table("projects")
                .select("name")
                .eq("id", row["project_id"])
                .execute()
            )
            project_name = pr.data[0]["name"] if pr.data else ""

        employee_name = ""
        if row.get("employees"):
            employee_name = row["employees"]["name"]
        elif row.get("employee_id"):
            er = (
                supabase.table("employees")
                .select("name")
                .eq("id", row["employee_id"])
                .execute()
            )
            employee_name = er.data[0]["name"] if er.data else ""

        deliverables = []
        if include_deliverables:
            deliverables = await self.get_deliverables(row["id"])

        # RF10: código único de tarea (determinístico desde id + año)
        created_year = datetime.fromisoformat(row["created_at"]).year
        task_code = f"TASK-{created_year}-{row['id']:04d}"

        return TaskResponse(
            id=row["id"],
            code=task_code,
            project_id=row["project_id"],
            project_name=project_name,
            employee_id=row["employee_id"],
            employee_name=employee_name,
            title=row["title"],
            description=row.get("description"),
            status=row["status"],
            priority=row["priority"],
            due_date=row.get("due_date"),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row.get("completed_at")
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deliverables=deliverables,
        )

    def _format_deliverable(self, row: dict) -> TaskDeliverableResponse:
        return TaskDeliverableResponse(
            id=row["id"],
            task_id=row["task_id"],
            file_name=row["file_name"],
            file_url=row["file_url"],
            file_size=row["file_size"],
            uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        )

    def _extract_storage_path(self, url: str) -> Optional[str]:
        marker = f"/object/public/{DELIVERABLES_BUCKET}/"
        if marker in url:
            return url.split(marker)[-1]
        return None

    async def _get_employee_id(self, user_id: str) -> Optional[int]:
        try:
            r = (
                supabase.table("employees")
                .select("id")
                .eq("user_id", user_id)
                .execute()
            )
            return r.data[0]["id"] if r.data else None
        except Exception:
            return None


task_service = TaskService()
