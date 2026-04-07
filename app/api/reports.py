from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.models.auth import UserResponse
from app.services.reports import report_service
from app.services.notifications import notification_service
from app.database import get_admin_supabase

from app.api.deps import get_current_user

router = APIRouter(tags=["reports"])

@router.get("/projects/{project_id}/report/pdf")
async def export_project_pdf(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Exporta el reporte completo de un proyecto como PDF.
    Acceso: managers y sponsors del proyecto.
    """
    if current_user.role not in ("manager", "sponsor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a este reporte",
        )

    # Sponsor can only export their own project
    if current_user.role == "sponsor":
        sb = get_admin_supabase()
        proj = sb.table("projects").select("sponsor_id").eq("id", project_id).execute()
        if not proj.data or proj.data[0].get("sponsor_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sin acceso a este proyecto",
            )

    try:
        pdf_bytes = await report_service.generate_project_report(project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF: {str(e)}",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="proyecto_{project_id}_reporte.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )

@router.get("/employees/{employee_id}/report/pdf")
async def export_employee_pdf(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Exporta el reporte de desempeño de un empleado como PDF.
    Acceso: managers (cualquier empleado) o el propio empleado.
    """
    if current_user.role not in ("manager", "employee"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a este reporte",
        )

    if current_user.role == "employee":
        sb = get_admin_supabase()
        emp_res = sb.table("employees").select("id").eq("user_id", current_user.id).execute()
        own_id = emp_res.data[0]["id"] if emp_res.data else None
        if own_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes exportar tu propio reporte",
            )

    try:
        pdf_bytes = await report_service.generate_employee_report(employee_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF: {str(e)}",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="empleado_{employee_id}_desempeno.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )

@router.post("/employees/{employee_id}/report/send-email", status_code=status.HTTP_200_OK)
async def send_employee_report_by_email(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Genera el informe de desempeño del empleado y lo envía por correo (RF16).

    Acceso:
    - Managers: pueden enviar el informe de cualquier empleado
    - Empleados: solo pueden solicitar el envío de su propio informe

    El PDF se envía al correo del empleado.
    """
    sb = get_admin_supabase()

    if current_user.role not in ("manager", "employee"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso")

    if current_user.role == "employee":
        emp_res = sb.table("employees").select("id").eq("user_id", current_user.id).execute()
        own_id = emp_res.data[0]["id"] if emp_res.data else None
        if own_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes solicitar tu propio informe",
            )

    # Obtener email del empleado
    emp_res = sb.table("employees").select("name, user_id").eq("id", employee_id).execute()
    if not emp_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado")

    emp = emp_res.data[0]
    user_res = sb.table("users").select("email").eq("id", emp["user_id"]).execute()
    if not user_res.data or not user_res.data[0].get("email"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el email del empleado",
        )

    employee_email = user_res.data[0]["email"]
    employee_name = emp["name"]

    # Generar PDF
    try:
        pdf_bytes = await report_service.generate_employee_report(employee_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF: {str(e)}",
        )

    # Enviar por email
    sent = await notification_service.send_employee_report_email(
        employee_email=employee_email,
        employee_name=employee_name,
        pdf_bytes=pdf_bytes,
        employee_id=employee_id,
    )

    return {
        "success": sent,
        "message": f"Informe {'enviado' if sent else 'en cola'} a {employee_email}",
        "employee_name": employee_name,
        "employee_email": employee_email,
    }
