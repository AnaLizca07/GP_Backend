"""
Servicio para generación de comprobantes de pago de nómina (PDF),
subida a Supabase Storage y envío por correo electrónico.
"""
import io
import uuid
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)

from app.database import get_admin_supabase
from app.config import settings

logger = logging.getLogger(__name__)


# ─── PDF ───────────────────────────────────────────────────────────────────

def generate_payroll_pdf(
    payroll_id: int,
    employee_name: str,
    employee_identification: str,
    period_start: str,
    period_end: str,
    base_salary: float,
    deductions: dict,
    employer_contributions: dict,
    benefits: dict,
    net_pay: float,
    paid_at: str,
) -> bytes:
    """Genera el PDF del comprobante y devuelve los bytes."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    blue   = colors.HexColor('#1e40af')
    red    = colors.HexColor('#dc2626')
    green  = colors.HexColor('#16a34a')
    amber  = colors.HexColor('#d97706')
    light  = colors.HexColor('#f9fafb')
    gray   = colors.HexColor('#6b7280')

    title_style = ParagraphStyle(
        'CT', parent=styles['Title'],
        fontSize=17, spaceAfter=4,
        alignment=TA_CENTER, textColor=blue
    )
    sub_style = ParagraphStyle(
        'CS', parent=styles['Normal'],
        fontSize=9, alignment=TA_CENTER, textColor=gray
    )
    section_style = ParagraphStyle(
        'SEC', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica-Bold',
        textColor=blue, spaceBefore=10, spaceAfter=3
    )
    footer_style = ParagraphStyle(
        'FT', parent=styles['Normal'],
        fontSize=8, textColor=gray, alignment=TA_CENTER
    )

    col_w = [13 * cm, 4 * cm]
    elements = []

    # ── Encabezado ──────────────────────────────────────────────────────────
    elements.append(Paragraph("COMPROBANTE DE PAGO DE NÓMINA", title_style))
    elements.append(Paragraph(
        f"No. NOM-{payroll_id:06d} &nbsp;&nbsp;|&nbsp;&nbsp; Fecha de pago: {paid_at}",
        sub_style
    ))
    elements.append(HRFlowable(
        width="100%", thickness=2, color=blue, spaceAfter=10
    ))

    # ── Datos del empleado ──────────────────────────────────────────────────
    elements.append(Paragraph("DATOS DEL EMPLEADO", section_style))
    emp_table = Table([
        ['Nombre completo:', employee_name],
        ['Identificación:', employee_identification],
        ['Período de pago:', f"{period_start}  al  {period_end}"],
    ], colWidths=[4 * cm, 13 * cm])
    emp_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(emp_table)
    elements.append(Spacer(1, 0.2 * cm))

    # ── Devengados ──────────────────────────────────────────────────────────
    elements.append(Paragraph("DEVENGADOS", section_style))
    earned_rows = [['Concepto', 'Valor']]
    earned_rows.append(['Salario base', f"$ {base_salary:,.0f}"])
    benefit_labels = {
        'cesantias': 'Cesantías (provisión mensual)',
        'intereses_cesantias': 'Intereses cesantías (provisión)',
        'prima_servicios': 'Prima de servicios (provisión)',
        'vacaciones': 'Vacaciones (provisión)',
    }
    for key, label in benefit_labels.items():
        val = (benefits or {}).get(key, 0)
        if val and val > 0:
            earned_rows.append([label, f"$ {val:,.0f}"])
    earned_rows.append(['TOTAL DEVENGADO', f"$ {base_salary:,.0f}"])
    _build_table(elements, earned_rows, col_w, blue, colors.HexColor('#dbeafe'))

    # ── Deducciones empleado ────────────────────────────────────────────────
    elements.append(Paragraph("DEDUCCIONES (A CARGO DEL EMPLEADO)", section_style))
    ded_labels = {
        'salud': 'Salud (4%)',
        'pension': 'Pensión (4%)',
        'fondo_solidaridad': 'Fondo solidaridad pensional',
        'otros': 'Otras deducciones',
    }
    ded_rows = [['Concepto', 'Valor']]
    total_ded = 0
    for key, label in ded_labels.items():
        val = (deductions or {}).get(key, 0)
        if val and val > 0:
            ded_rows.append([label, f"$ {val:,.0f}"])
            total_ded += val
    ded_rows.append(['TOTAL DEDUCCIONES', f"$ {total_ded:,.0f}"])
    _build_table(elements, ded_rows, col_w, red, colors.HexColor('#fee2e2'), total_color=red)

    # ── Aportes patronales (informativo) ────────────────────────────────────
    elements.append(Paragraph(
        "APORTES PATRONALES (A CARGO DE LA EMPRESA — INFORMATIVO)", section_style
    ))
    emp_labels = {
        'salud': 'Salud empleador (8.5%)',
        'pension': 'Pensión empleador (12%)',
        'arl': 'ARL',
        'caja_compensacion': 'Caja de compensación (4%)',
        'icbf': 'ICBF (3%)',
        'sena': 'SENA (2%)',
    }
    emp_rows = [['Concepto', 'Valor']]
    total_emp = 0
    for key, label in emp_labels.items():
        val = (employer_contributions or {}).get(key, 0)
        if val and val > 0:
            emp_rows.append([label, f"$ {val:,.0f}"])
            total_emp += val
    emp_rows.append(['TOTAL APORTES PATRONALES', f"$ {total_emp:,.0f}"])
    _build_table(elements, emp_rows, col_w, amber, colors.HexColor('#fef3c7'),
                 total_color=colors.HexColor('#92400e'))

    elements.append(Spacer(1, 0.4 * cm))

    # ── Neto a pagar ────────────────────────────────────────────────────────
    net_table = Table(
        [['SALARIO NETO A PAGAR', f"$ {net_pay:,.0f}"]],
        colWidths=col_w
    )
    net_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), green),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 13),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(net_table)
    elements.append(Spacer(1, 1 * cm))

    # ── Pie de página ───────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=gray, spaceAfter=6))
    elements.append(Paragraph(
        "Este documento es un comprobante oficial de pago de nómina generado automáticamente por PMIS.",
        footer_style
    ))
    elements.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}",
        footer_style
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _build_table(elements, rows, col_w, header_color, total_bg, total_color=None):
    """Helper para construir tablas de nómina con estilo consistente."""
    light = colors.HexColor('#f9fafb')
    table = Table(rows, colWidths=col_w)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), total_bg),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, light]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    if total_color:
        style.append(('TEXTCOLOR', (0, -1), (-1, -1), total_color))
    table.setStyle(TableStyle(style))
    elements.append(table)


# ─── Storage ───────────────────────────────────────────────────────────────

def upload_pdf_to_storage(pdf_bytes: bytes, payroll_id: int) -> str:
    """Sube el PDF a Supabase Storage y devuelve la URL pública."""
    admin = get_admin_supabase()
    filename = f"payroll/recibo_nomina_{payroll_id}_{uuid.uuid4().hex[:8]}.pdf"

    try:
        admin.storage.from_("resumes").upload(
            file=pdf_bytes,
            path=filename,
            file_options={"content-type": "application/pdf"},
        )
    except Exception as e:
        # Si el bucket no existe, intentar crear uno público y reintentar
        logger.warning(f"Error subiendo a 'resumes', intentando bucket 'payroll-receipts': {e}")
        try:
            admin.storage.create_bucket("payroll-receipts", options={"public": True})
        except Exception:
            pass
        admin.storage.from_("payroll-receipts").upload(
            file=pdf_bytes,
            path=f"recibo_nomina_{payroll_id}_{uuid.uuid4().hex[:8]}.pdf",
            file_options={"content-type": "application/pdf"},
        )
        return admin.storage.from_("payroll-receipts").get_public_url(
            f"recibo_nomina_{payroll_id}_{uuid.uuid4().hex[:8]}.pdf"
        )

    return admin.storage.from_("resumes").get_public_url(filename)


# ─── Email ─────────────────────────────────────────────────────────────────

def send_payroll_email(
    to_email: str,
    employee_name: str,
    period_start: str,
    period_end: str,
    net_pay: float,
    pdf_bytes: bytes,
    receipt_url: Optional[str] = None,
) -> bool:
    """Envía el comprobante de pago por correo con el PDF adjunto."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP no configurado — omitiendo envío de email de nómina")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
        msg["To"]      = to_email
        msg["Subject"] = f"Comprobante de pago de nómina — {period_start} al {period_end}"

        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#1f2937;max-width:600px;margin:auto;">
          <div style="background:#1e40af;padding:24px;border-radius:8px 8px 0 0;">
            <h1 style="color:white;margin:0;font-size:20px;">Comprobante de Pago de Nómina</h1>
            <p style="color:#bfdbfe;margin:6px 0 0;">PMIS — Sistema de Gestión</p>
          </div>
          <div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;">
            <p>Hola <strong>{employee_name}</strong>,</p>
            <p>Te informamos que tu pago de nómina correspondiente al período
               <strong>{period_start}</strong> al <strong>{period_end}</strong> ha sido procesado.</p>
            <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px;margin:20px 0;text-align:center;">
              <p style="margin:0;color:#15803d;font-size:13px;">SALARIO NETO PAGADO</p>
              <p style="margin:8px 0 0;color:#166534;font-size:28px;font-weight:bold;">
                $ {net_pay:,.0f} COP
              </p>
            </div>
            <p>El comprobante detallado con el desglose completo de deducciones y aportes
               se encuentra adjunto a este correo en formato PDF.</p>
            {"<p><a href='" + receipt_url + "' style='color:#1e40af;'>Ver comprobante en línea</a></p>" if receipt_url else ""}
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
            <p style="font-size:12px;color:#9ca3af;">
              Este es un correo automático generado por PMIS. Por favor no respondas a este mensaje.
            </p>
          </div>
        </html></body>
        """

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Adjuntar PDF
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename=\"comprobante_nomina_{period_start}_{period_end}.pdf\""
        )
        msg.attach(part)

        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT

        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)

        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email de nómina enviado a {to_email}")
        return True

    except Exception as e:
        logger.error(f"Error enviando email de nómina a {to_email}: {e}")
        return False


# ─── Orquestador ───────────────────────────────────────────────────────────

async def process_payroll_receipt(
    payroll_id: int,
    employee_id: int,
    employee_name: str,
    period_start: str,
    period_end: str,
    base_salary: float,
    deductions: dict,
    employer_contributions: dict,
    benefits: dict,
    net_pay: float,
) -> Optional[str]:
    """
    Genera el PDF, lo sube a Storage, envía el email y devuelve la receipt_url.
    Si algo falla parcialmente, registra el error pero no interrumpe el flujo.
    """
    paid_at = datetime.now().strftime("%d/%m/%Y")

    # 1. Obtener email del empleado
    employee_email: Optional[str] = None
    employee_identification: str = "—"
    try:
        admin = get_admin_supabase()
        emp_result = admin.table("employees").select("identification, user_id").eq("id", employee_id).execute()
        if emp_result.data:
            employee_identification = emp_result.data[0].get("identification", "—")
            user_id = emp_result.data[0].get("user_id")
            if user_id:
                user_result = admin.auth.admin.get_user_by_id(user_id)
                if user_result and user_result.user:
                    employee_email = user_result.user.email
    except Exception as e:
        logger.warning(f"No se pudo obtener email del empleado {employee_id}: {e}")

    # 2. Generar PDF
    try:
        pdf_bytes = generate_payroll_pdf(
            payroll_id=payroll_id,
            employee_name=employee_name,
            employee_identification=employee_identification,
            period_start=period_start,
            period_end=period_end,
            base_salary=base_salary,
            deductions=deductions,
            employer_contributions=employer_contributions,
            benefits=benefits,
            net_pay=net_pay,
            paid_at=paid_at,
        )
    except Exception as e:
        logger.error(f"Error generando PDF de nómina {payroll_id}: {e}")
        return None

    # 3. Subir a Storage
    receipt_url: Optional[str] = None
    try:
        receipt_url = upload_pdf_to_storage(pdf_bytes, payroll_id)
    except Exception as e:
        logger.error(f"Error subiendo PDF de nómina {payroll_id} a Storage: {e}")

    # 4. Enviar email (no bloquea si falla)
    if employee_email:
        send_payroll_email(
            to_email=employee_email,
            employee_name=employee_name,
            period_start=period_start,
            period_end=period_end,
            net_pay=net_pay,
            pdf_bytes=pdf_bytes,
            receipt_url=receipt_url,
        )
    else:
        logger.warning(f"Sin email para empleado {employee_id} — comprobante generado pero no enviado")

    return receipt_url
