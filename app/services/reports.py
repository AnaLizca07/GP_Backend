import io
import logging
from datetime import date, datetime
from typing import Optional

from app.database import get_admin_supabase
from app.services.kpis import kpi_service

logger = logging.getLogger(__name__)


def _supabase():
    return get_admin_supabase()


class ReportService:

    # -------------------------------------------------------------------------
    # PROJECT REPORT PDF
    # -------------------------------------------------------------------------

    async def generate_project_report(self, project_id: int) -> bytes:
        """Generate a PDF report for a project using ReportLab."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )

        kpis = await kpi_service.get_project_kpis(project_id)
        if kpis is None:
            raise ValueError("Proyecto no encontrado")

        perf = await kpi_service.get_project_employee_performance(project_id)

        # Tasks detail
        sb = _supabase()
        tasks_res = (
            sb.table("tasks")
            .select("title, status, priority, due_date, employees(name)")
            .eq("project_id", project_id)
            .order("status")
            .execute()
        )
        tasks = tasks_res.data or []

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        brand_color = colors.HexColor("#003C68")

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            textColor=brand_color,
            fontSize=20,
            spaceAfter=6,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            textColor=brand_color,
            fontSize=13,
            spaceBefore=14,
            spaceAfter=4,
        )
        normal = styles["Normal"]

        STATUS_MAP = {
            "active": "Activo",
            "planning": "Planificación",
            "on_hold": "En Pausa",
            "completed": "Completado",
            "cancelled": "Cancelado",
        }
        TASK_STATUS_MAP = {
            "pending": "Pendiente",
            "in_progress": "En Progreso",
            "completed": "Completada",
            "blocked": "Bloqueada",
            "review": "En Revisión",
        }
        PRIORITY_MAP = {
            "low": "Baja",
            "medium": "Media",
            "high": "Alta",
            "urgent": "Urgente",
        }

        story = []

        # Header
        story.append(Paragraph(f"Reporte de Proyecto", title_style))
        story.append(Paragraph(kpis["project_name"], styles["Heading1"]))
        story.append(Paragraph(f"Generado: {date.today().strftime('%d/%m/%Y')}", normal))
        story.append(HRFlowable(width="100%", thickness=2, color=brand_color, spaceAfter=10))

        # Overview
        story.append(Paragraph("Resumen General", h2_style))
        overview_data = [
            ["Estado", STATUS_MAP.get(kpis["status"], kpis["status"])],
            ["Fecha de inicio", kpis.get("start_date") or "—"],
            ["Fecha de fin", kpis.get("end_date") or "—"],
            ["Días transcurridos", str(kpis["days_elapsed"])],
            ["Días restantes", str(kpis["days_remaining"])],
            ["Presupuesto", f"${kpis['budget']:,.2f}" if kpis["budget"] else "—"],
            ["Tamaño del equipo", str(kpis["team_size"])],
        ]
        overview_table = Table(overview_data, colWidths=[5 * cm, 10 * cm])
        overview_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF4FA")),
                ("TEXTCOLOR", (0, 0), (0, -1), brand_color),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(overview_table)

        # Task KPIs
        story.append(Paragraph("KPIs de Tareas", h2_style))
        total = kpis["total_tasks"]
        completed = kpis["completed_tasks"]
        pct = kpis["progress_percentage"]
        task_kpi_data = [
            ["Métrica", "Valor"],
            ["Total de tareas", str(total)],
            ["Completadas", str(completed)],
            ["En Progreso", str(kpis["in_progress_tasks"])],
            ["Pendientes", str(kpis["pending_tasks"])],
            ["Bloqueadas", str(kpis["blocked_tasks"])],
            ["Vencidas", str(kpis["overdue_tasks"])],
            ["Avance general", f"{pct}%"],
        ]
        t = Table(task_kpi_data, colWidths=[7 * cm, 7 * cm])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ])
        )
        story.append(t)

        # Team performance
        if perf and perf.get("members"):
            story.append(Paragraph("Desempeño del Equipo", h2_style))
            members_data = [
                ["Empleado", "Cargo", "Dedicación", "Tareas", "Completadas", "Avance"],
            ]
            for m in perf["members"]:
                members_data.append([
                    m["employee_name"],
                    m["position"],
                    f"{m['dedication_percentage']:.0f}%",
                    str(m["total_tasks"]),
                    str(m["completed_tasks"]),
                    f"{m['completion_rate']:.1f}%",
                ])
            mt = Table(members_data, colWidths=[4 * cm, 3.5 * cm, 2.5 * cm, 2 * cm, 2.5 * cm, 2.5 * cm])
            mt.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ])
            )
            story.append(mt)

        # Tasks list
        if tasks:
            story.append(Paragraph("Listado de Tareas", h2_style))
            tasks_data = [["Tarea", "Responsable", "Estado", "Prioridad", "Vencimiento"]]
            for t_row in tasks:
                emp_name = ""
                if t_row.get("employees"):
                    emp_name = t_row["employees"].get("name", "")
                due = t_row.get("due_date") or "—"
                if due != "—":
                    try:
                        due = date.fromisoformat(due[:10]).strftime("%d/%m/%Y")
                    except Exception:
                        pass
                tasks_data.append([
                    t_row.get("title", ""),
                    emp_name,
                    TASK_STATUS_MAP.get(t_row.get("status", ""), t_row.get("status", "")),
                    PRIORITY_MAP.get(t_row.get("priority", ""), t_row.get("priority", "")),
                    due,
                ])
            tt = Table(tasks_data, colWidths=[5 * cm, 3.5 * cm, 2.5 * cm, 2 * cm, 2.5 * cm])
            tt.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("ALIGN", (3, 0), (-1, -1), "CENTER"),
                    ("ALIGN", (4, 0), (-1, -1), "CENTER"),
                ])
            )
            story.append(tt)

        # Footer note
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
        story.append(
            Paragraph(
                f"<font color='grey' size='8'>Reporte generado automáticamente por ProjeGest — {datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
                normal,
            )
        )

        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    # -------------------------------------------------------------------------
    # EMPLOYEE PERFORMANCE REPORT PDF
    # -------------------------------------------------------------------------

    async def generate_employee_report(self, employee_id: int) -> bytes:
        """Generate a PDF performance report for an employee using ReportLab."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )

        perf = await kpi_service.get_employee_performance(employee_id)
        if perf is None:
            raise ValueError("Empleado no encontrado")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        brand_color = colors.HexColor("#003C68")

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            textColor=brand_color,
            fontSize=20,
            spaceAfter=6,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            textColor=brand_color,
            fontSize=13,
            spaceBefore=14,
            spaceAfter=4,
        )
        normal = styles["Normal"]

        story = []

        story.append(Paragraph("Reporte de Desempeño", title_style))
        story.append(Paragraph(perf["employee_name"], styles["Heading1"]))
        story.append(Paragraph(perf.get("position", ""), normal))
        story.append(Paragraph(f"Generado: {date.today().strftime('%d/%m/%Y')}", normal))
        story.append(HRFlowable(width="100%", thickness=2, color=brand_color, spaceAfter=10))

        # KPI summary
        story.append(Paragraph("Métricas de Desempeño", h2_style))
        kpi_data = [
            ["Métrica", "Valor"],
            ["Total de tareas", str(perf["total_tasks"])],
            ["Tareas completadas", str(perf["completed_tasks"])],
            ["En progreso", str(perf["in_progress_tasks"])],
            ["Pendientes", str(perf["pending_tasks"])],
            ["Bloqueadas", str(perf["blocked_tasks"])],
            ["Vencidas", str(perf["overdue_tasks"])],
            ["Tasa de completitud", f"{perf['completion_rate']:.1f}%"],
        ]
        kt = Table(kpi_data, colWidths=[7 * cm, 7 * cm])
        kt.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ])
        )
        story.append(kt)

        # Projects
        if perf.get("assigned_projects"):
            story.append(Paragraph("Proyectos Asignados", h2_style))
            proj_data = [["Proyecto", "Estado", "Dedicación"]]
            STATUS_MAP = {
                "active": "Activo",
                "planning": "Planificación",
                "on_hold": "En Pausa",
                "completed": "Completado",
                "cancelled": "Cancelado",
            }
            for p in perf["assigned_projects"]:
                proj_data.append([
                    p["project_name"],
                    STATUS_MAP.get(p["project_status"], p["project_status"]),
                    f"{p['dedication_percentage']:.0f}%",
                ])
            pt = Table(proj_data, colWidths=[8 * cm, 4 * cm, 3 * cm])
            pt.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("PADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ])
            )
            story.append(pt)

        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
        story.append(
            Paragraph(
                f"<font color='grey' size='8'>Reporte generado automáticamente por ProjeGest — {datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
                normal,
            )
        )

        doc.build(story)
        buffer.seek(0)
        return buffer.read()


report_service = ReportService()
