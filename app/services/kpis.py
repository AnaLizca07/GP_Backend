import logging
from typing import Optional
from datetime import date, datetime

from app.database import get_admin_supabase

logger = logging.getLogger(__name__)


def _supabase():
    return get_admin_supabase()


class KpiService:

    # -------------------------------------------------------------------------
    # PROJECT KPIs (manager)
    # -------------------------------------------------------------------------

    async def get_project_kpis(self, project_id: int) -> Optional[dict]:
        try:
            sb = _supabase()

            # Project data
            proj_res = (
                sb.table("projects")
                .select("id, name, status, start_date, end_date, budget")
                .eq("id", project_id)
                .execute()
            )
            if not proj_res.data:
                return None
            project = proj_res.data[0]

            # Tasks
            tasks_res = (
                sb.table("tasks")
                .select("id, status, due_date, priority")
                .eq("project_id", project_id)
                .execute()
            )
            tasks = tasks_res.data or []

            total = len(tasks)
            completed = sum(1 for t in tasks if t["status"] == "completed")
            in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
            pending = sum(1 for t in tasks if t["status"] == "pending")
            blocked = sum(1 for t in tasks if t["status"] == "blocked")
            progress_pct = round(completed / total * 100, 1) if total > 0 else 0.0

            today = date.today()
            overdue = 0
            for t in tasks:
                if t.get("due_date") and t["status"] != "completed":
                    try:
                        due = date.fromisoformat(t["due_date"][:10])
                        if due < today:
                            overdue += 1
                    except Exception:
                        pass

            # Date progress
            start_date = project.get("start_date")
            end_date = project.get("end_date")
            days_elapsed = 0
            total_days = 0
            days_remaining = 0
            if start_date:
                try:
                    start = date.fromisoformat(start_date[:10])
                    days_elapsed = max(0, (today - start).days)
                    if end_date:
                        end = date.fromisoformat(end_date[:10])
                        total_days = max(1, (end - start).days)
                        days_remaining = max(0, (end - today).days)
                except Exception:
                    pass

            # Team size
            team_res = (
                sb.table("project_employees")
                .select("id", count="exact")
                .eq("project_id", project_id)
                .execute()
            )
            team_size = team_res.count or 0

            # Budget
            budget = float(project.get("budget") or 0)

            return {
                "project_id": project_id,
                "project_name": project["name"],
                "status": project["status"],
                # Task KPIs
                "total_tasks": total,
                "completed_tasks": completed,
                "in_progress_tasks": in_progress,
                "pending_tasks": pending,
                "blocked_tasks": blocked,
                "progress_percentage": progress_pct,
                "overdue_tasks": overdue,
                # Date KPIs
                "start_date": start_date,
                "end_date": end_date,
                "days_elapsed": days_elapsed,
                "total_days": total_days,
                "days_remaining": days_remaining,
                # Team
                "team_size": team_size,
                # Budget
                "budget": budget,
            }
        except Exception as e:
            logger.error(f"Error en get_project_kpis({project_id}): {e}")
            raise

    # -------------------------------------------------------------------------
    # SPONSOR PROGRESS (sponsor)
    # -------------------------------------------------------------------------

    async def get_sponsor_progress(self, project_id: int, sponsor_id: str) -> Optional[dict]:
        try:
            sb = _supabase()

            proj_res = (
                sb.table("projects")
                .select("id, name, status, start_date, end_date, budget, sponsor_id")
                .eq("id", project_id)
                .execute()
            )
            if not proj_res.data:
                return None
            project = proj_res.data[0]

            # Sponsors can only see their own projects
            if project.get("sponsor_id") != sponsor_id:
                return None

            tasks_res = (
                sb.table("tasks")
                .select("id, status, priority, due_date")
                .eq("project_id", project_id)
                .execute()
            )
            tasks = tasks_res.data or []

            total = len(tasks)
            completed = sum(1 for t in tasks if t["status"] == "completed")
            in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
            progress_pct = round(completed / total * 100, 1) if total > 0 else 0.0

            today = date.today()
            overdue = 0
            for t in tasks:
                if t.get("due_date") and t["status"] != "completed":
                    try:
                        due = date.fromisoformat(t["due_date"][:10])
                        if due < today:
                            overdue += 1
                    except Exception:
                        pass

            days_remaining = 0
            end_date = project.get("end_date")
            if end_date:
                try:
                    end = date.fromisoformat(end_date[:10])
                    days_remaining = max(0, (end - today).days)
                except Exception:
                    pass

            budget = float(project.get("budget") or 0)

            return {
                "project_id": project_id,
                "project_name": project["name"],
                "status": project["status"],
                "start_date": project.get("start_date"),
                "end_date": end_date,
                "days_remaining": days_remaining,
                "total_tasks": total,
                "completed_tasks": completed,
                "in_progress_tasks": in_progress,
                "progress_percentage": progress_pct,
                "overdue_tasks": overdue,
                "budget": budget,
            }
        except Exception as e:
            logger.error(f"Error en get_sponsor_progress({project_id}): {e}")
            raise

    # -------------------------------------------------------------------------
    # EMPLOYEE PERFORMANCE
    # -------------------------------------------------------------------------

    async def get_employee_performance(self, employee_id: int) -> Optional[dict]:
        try:
            sb = _supabase()

            emp_res = (
                sb.table("employees")
                .select("id, name, position, status")
                .eq("id", employee_id)
                .execute()
            )
            if not emp_res.data:
                return None
            employee = emp_res.data[0]

            tasks_res = (
                sb.table("tasks")
                .select("id, status, due_date, priority, project_id")
                .eq("employee_id", employee_id)
                .execute()
            )
            tasks = tasks_res.data or []

            total = len(tasks)
            completed = sum(1 for t in tasks if t["status"] == "completed")
            in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
            pending = sum(1 for t in tasks if t["status"] == "pending")
            blocked = sum(1 for t in tasks if t["status"] == "blocked")
            completion_rate = round(completed / total * 100, 1) if total > 0 else 0.0

            today = date.today()
            overdue = 0
            for t in tasks:
                if t.get("due_date") and t["status"] != "completed":
                    try:
                        due = date.fromisoformat(t["due_date"][:10])
                        if due < today:
                            overdue += 1
                    except Exception:
                        pass

            # Unique projects
            project_ids = list({t["project_id"] for t in tasks if t.get("project_id")})

            # Project assignments with dedication
            assign_res = (
                sb.table("project_employees")
                .select("project_id, dedication_percentage, projects(id, name, status)")
                .eq("employee_id", employee_id)
                .execute()
            )
            projects = []
            for row in assign_res.data or []:
                proj = row.get("projects") or {}
                projects.append({
                    "project_id": row["project_id"],
                    "project_name": proj.get("name", ""),
                    "project_status": proj.get("status", ""),
                    "dedication_percentage": float(row.get("dedication_percentage") or 0),
                })

            return {
                "employee_id": employee_id,
                "employee_name": employee["name"],
                "position": employee["position"],
                "total_tasks": total,
                "completed_tasks": completed,
                "in_progress_tasks": in_progress,
                "pending_tasks": pending,
                "blocked_tasks": blocked,
                "overdue_tasks": overdue,
                "completion_rate": completion_rate,
                "assigned_projects": projects,
            }
        except Exception as e:
            logger.error(f"Error en get_employee_performance({employee_id}): {e}")
            raise

    # -------------------------------------------------------------------------
    # PROJECT EMPLOYEE PERFORMANCE (manager)
    # -------------------------------------------------------------------------

    async def get_project_employee_performance(self, project_id: int) -> Optional[dict]:
        try:
            sb = _supabase()

            # Verify project exists
            proj_res = (
                sb.table("projects")
                .select("id, name")
                .eq("id", project_id)
                .execute()
            )
            if not proj_res.data:
                return None
            project = proj_res.data[0]

            # Employees assigned to project
            assign_res = (
                sb.table("project_employees")
                .select("employee_id, dedication_percentage, employees(id, name, position)")
                .eq("project_id", project_id)
                .execute()
            )
            assignments = assign_res.data or []

            # All tasks for project
            tasks_res = (
                sb.table("tasks")
                .select("id, employee_id, status, due_date, priority")
                .eq("project_id", project_id)
                .execute()
            )
            all_tasks = tasks_res.data or []

            today = date.today()
            members = []
            for a in assignments:
                emp_id = a["employee_id"]
                emp_info = a.get("employees") or {}
                emp_tasks = [t for t in all_tasks if t["employee_id"] == emp_id]

                total = len(emp_tasks)
                completed = sum(1 for t in emp_tasks if t["status"] == "completed")
                in_progress = sum(1 for t in emp_tasks if t["status"] == "in_progress")
                pending = sum(1 for t in emp_tasks if t["status"] == "pending")
                overdue = 0
                for t in emp_tasks:
                    if t.get("due_date") and t["status"] != "completed":
                        try:
                            due = date.fromisoformat(t["due_date"][:10])
                            if due < today:
                                overdue += 1
                        except Exception:
                            pass

                completion_rate = round(completed / total * 100, 1) if total > 0 else 0.0

                members.append({
                    "employee_id": emp_id,
                    "employee_name": emp_info.get("name", ""),
                    "position": emp_info.get("position", ""),
                    "dedication_percentage": float(a.get("dedication_percentage") or 0),
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "in_progress_tasks": in_progress,
                    "pending_tasks": pending,
                    "overdue_tasks": overdue,
                    "completion_rate": completion_rate,
                })

            return {
                "project_id": project_id,
                "project_name": project["name"],
                "members": members,
            }
        except Exception as e:
            logger.error(f"Error en get_project_employee_performance({project_id}): {e}")
            raise

    # -------------------------------------------------------------------------
    # PERFORMANCE INDICES — SPI & CPI por proyecto (manager)
    # -------------------------------------------------------------------------

    async def get_performance_indices(self, user_id: str) -> list[dict]:
        """
        Calcula SPI (Schedule Performance Index) y CPI (Cost Performance Index)
        para los proyectos del gerente usando Earned Value Management (EVM).

        EV  = (completadas / total_tareas) × presupuesto
        AC  = suma de transacciones tipo 'expense'
        PV  = (días_transcurridos / duración_total) × presupuesto
        CPI = EV / AC   (eficiencia de costo; >1 = bajo presupuesto)
        SPI = EV / PV   (eficiencia de cronograma; >1 = adelantado)
        """
        try:
            sb = _supabase()
            today = date.today()

            projects_res = (
                sb.table("projects")
                .select("id, name, status, budget, start_date, end_date")
                .eq("created_by", user_id)
                .execute()
            )
            projects = projects_res.data or []

            result = []
            for p in projects:
                project_id = p["id"]
                budget = float(p.get("budget") or 0)

                # ── Earned Value (EV) via task completion ─────────────────
                tasks_res = (
                    sb.table("tasks")
                    .select("id, status")
                    .eq("project_id", project_id)
                    .execute()
                )
                tasks = tasks_res.data or []
                total_tasks = len(tasks)
                completed_tasks = sum(1 for t in tasks if t["status"] == "completed")
                progress_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
                ev = (progress_pct / 100.0) * budget

                # ── Actual Cost (AC) via expense transactions ─────────────
                tx_res = (
                    sb.table("transactions")
                    .select("amount, type")
                    .eq("project_id", project_id)
                    .execute()
                )
                txs = tx_res.data or []
                ac = sum(float(t["amount"]) for t in txs if t["type"] == "expense")

                # ── CPI ───────────────────────────────────────────────────
                cpi = round(ev / ac, 3) if ac > 0 else 1.0

                # ── Planned Value (PV) via time progress ──────────────────
                spi = 1.0
                start_str = p.get("start_date")
                end_str = p.get("end_date")
                if start_str and end_str and budget > 0:
                    try:
                        start = date.fromisoformat(start_str[:10])
                        end = date.fromisoformat(end_str[:10])
                        total_days = max(1, (end - start).days)
                        elapsed_days = max(0, (today - start).days)
                        time_pct = min(elapsed_days / total_days, 1.0)
                        pv = time_pct * budget
                        spi = round(ev / pv, 3) if pv > 0 else 1.0
                    except Exception:
                        spi = 1.0

                result.append({
                    "id": project_id,
                    "name": p["name"],
                    "status": p["status"],
                    "cpi": cpi,
                    "spi": spi,
                    "progress_pct": round(progress_pct, 1),
                    "budget": budget,
                    "spent": ac,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                })

            return result
        except Exception as e:
            logger.error(f"Error en get_performance_indices: {e}")
            raise


kpi_service = KpiService()
