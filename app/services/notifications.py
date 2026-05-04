import secrets
import string
import logging
import json
import base64
import asyncio
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Optional, Dict, Any, List, Tuple
from fastapi import HTTPException

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

class NotificationService:
    def __init__(self):
        self._load_brevo_config()

    def _load_brevo_config(self):
        try:
            from app.config import settings
            self.brevo_api_key = settings.BREVO_API_KEY or ""
            self.from_email = settings.SMTP_FROM_EMAIL or ""
            self.from_name = settings.SMTP_FROM_NAME or "ProjeGest"
        except Exception as e:
            logger.error(f"Error loading Brevo config: {e}")
            import os
            self.brevo_api_key = os.getenv("BREVO_API_KEY", "")
            self.from_email = os.getenv("SMTP_FROM_EMAIL", "")
            self.from_name = os.getenv("SMTP_FROM_NAME", "ProjeGest")

        self.configured = bool(self.brevo_api_key and self.from_email)
        if self.configured:
            logger.info("Brevo API configured successfully")
        else:
            logger.warning("Brevo API not configured — emails will be skipped")

    def _send_brevo_request(self, payload: dict) -> bool:
        """Llamada síncrona a la API de Brevo (se ejecuta en thread executor)."""
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            BREVO_API_URL,
            data=data,
            headers={
                "api-key": self.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=15) as resp:
                status = resp.status
                if status in (200, 201):
                    return True
                logger.error(f"Brevo API error status {status}")
                return False
        except Exception as e:
            logger.error(f"Brevo API request failed: {e}")
            return False

    async def _send_email(self, to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        """Enviar email via Brevo HTTP API (no bloquea el event loop)."""
        if not self.configured:
            logger.warning(f"Brevo not configured — skipping email to {to_email}")
            return False
        payload = {
            "sender": {"name": self.from_name, "email": self.from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
            "textContent": text_content,
        }
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_brevo_request, payload)

    async def _send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        attachments: List[Tuple[str, bytes, str]],
    ) -> bool:
        """Enviar email con adjuntos via Brevo HTTP API."""
        if not self.configured:
            logger.warning(f"Brevo not configured — skipping email with attachment to {to_email}")
            return False
        attachment_list = [
            {"content": base64.b64encode(data).decode("utf-8"), "name": filename}
            for filename, data, _ in attachments
        ]
        payload = {
            "sender": {"name": self.from_name, "email": self.from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
            "textContent": text_content,
            "attachment": attachment_list,
        }
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_brevo_request, payload)

    def generate_temporary_password(self, length: int = 12) -> str:
        """
        Generar contraseña temporal segura

        Criterios:
        - Minimo 12 caracteres
        - Contiene mayúsculas, minúsculas, números y símbolos
        - Fácil de transcribir (evita caracteres confusos como 0/O, l/1)
        """
        # Caracteres seguros y fáciles de leer
        lowercase = 'abcdefghijkmnpqrstuvwxyz'  # Sin 'l' y 'o'
        uppercase = 'ABCDEFGHJKLMNPQRSTUVWXYZ'  # Sin 'I' y 'O'
        digits = '23456789'  # Sin '0' y '1'
        symbols = '@#$%&*+-=?'  # Símbolos comunes y seguros

        # Asegurar al menos uno de cada tipo
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(symbols)
        ]

        # Completar longitud restante
        all_chars = lowercase + uppercase + digits + symbols
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))

        # Mezclar la contraseña
        secrets.SystemRandom().shuffle(password)

        return ''.join(password)

    async def send_employee_welcome_email(self, email: str, name: str, temporary_password: str) -> bool:
        """
        Enviar email de bienvenida con credenciales temporales usando SMTP directo
        """
        try:
            # HTML del email de bienvenida
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Bienvenido al Sistema PMIS</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; }}
                    .header {{ background: #007bff; color: white; padding: 30px 20px; text-align: center; }}
                    .content {{ padding: 30px 20px; background: #f8f9fa; }}
                    .credentials {{ background: #e9ecef; padding: 20px; margin: 20px 0; border-left: 4px solid #007bff; border-radius: 4px; }}
                    .important {{ background: #fff3cd; padding: 20px; margin: 20px 0; border-left: 4px solid #ffc107; border-radius: 4px; }}
                    .button {{ display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ background: #343a40; color: white; padding: 20px; text-align: center; font-size: 14px; }}
                    code {{ background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: monospace; color: #e83e8c; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎉 ¡Bienvenido/a {name}!</h1>
                        <p>Tu cuenta ha sido creada exitosamente</p>
                    </div>
                    <div class="content">
                        <h2>🏢 Sistema PMIS</h2>
                        <p>Hola {name},</p>
                        <p>Tu cuenta ha sido creada exitosamente en el <strong>Sistema PMIS</strong>. A continuación encontrarás tus credenciales de acceso:</p>

                        <div class="credentials">
                            <h3>📧 Credenciales de Acceso</h3>
                            <p><strong>Email:</strong> {email}</p>
                            <p><strong>Contraseña temporal:</strong> <code>{temporary_password}</code></p>
                        </div>

                        <div class="important">
                            <h3>🔐 IMPORTANTE - Medidas de Seguridad</h3>
                            <ul>
                                <li><strong>Debes cambiar tu contraseña</strong> en el primer inicio de sesión</li>
                                <li>Esta contraseña temporal <strong>expira en 24 horas</strong></li>
                                <li>Mantén esta información <strong>segura y confidencial</strong></li>
                                <li>No compartas estas credenciales con nadie</li>
                            </ul>
                        </div>

                        <div style="text-align: center; margin: 30px 0;">
                            <a href="https://gp-frontend-ebon.vercel.app/login" class="button">🚀 Acceder al Sistema</a>
                        </div>

                        <h3>📞 ¿Necesitas Ayuda?</h3>
                        <p>Si tienes problemas para acceder o necesitas asistencia, contacta a tu supervisor inmediato o al administrador del sistema.</p>

                        <p><strong>¡Éxito en tu nuevo rol!</strong> 🚀</p>
                    </div>
                    <div class="footer">
                        <p>Este es un mensaje automático del Sistema PMIS</p>
                        <p>Por favor, no respondas a este correo</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Texto plano como fallback
            text_content = f"""
            ¡Bienvenido/a {name}!

            Tu cuenta ha sido creada exitosamente en el Sistema PMIS.

            📧 CREDENCIALES DE ACCESO:
            Email: {email}
            Contraseña temporal: {temporary_password}

            🔐 IMPORTANTE - MEDIDAS DE SEGURIDAD:
            - Debes cambiar tu contraseña en el primer inicio de sesión
            - Esta contraseña temporal expira en 24 horas
            - Mantén esta información segura y confidencial
            - No compartas estas credenciales con nadie

            📞 ¿NECESITAS AYUDA?
            Si tienes problemas para acceder o necesitas asistencia, contacta a tu supervisor inmediato o al administrador del sistema.

            ¡Éxito en tu nuevo rol! 🚀

            ---
            Este es un mensaje automático del Sistema PMIS
            Por favor, no respondas a este correo
            """

            success = await self._send_email(
                to_email=email,
                subject="🎉 ¡Bienvenido al Sistema PMIS! - Credenciales de Acceso",
                html_content=html_content,
                text_content=text_content,
            )

            if success:
                logger.info(f"Welcome email sent successfully to {email}")
            else:
                logger.error(f"Error sending welcome email to {email}")

            return success

        except Exception as e:
            logger.error(f"General error in welcome email: {e}")
            return False

    async def send_password_reset_notification(self, email: str, name: str = "") -> bool:
        """
        Enviar notificación de reset de contraseña usando SMTP directo
        """
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Cambio de Contraseña Requerido</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; }}
                    .header {{ background: #ffc107; color: #212529; padding: 30px 20px; text-align: center; }}
                    .content {{ padding: 30px 20px; background: #f8f9fa; }}
                    .alert {{ background: #fff3cd; padding: 20px; margin: 20px 0; border-left: 4px solid #ffc107; border-radius: 4px; }}
                    .button {{ display: inline-block; background: #ffc107; color: #212529; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ background: #343a40; color: white; padding: 20px; text-align: center; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔄 Cambio de Contraseña Requerido</h1>
                    </div>
                    <div class="content">
                        <p>Hola {name or 'Usuario'},</p>

                        <div class="alert">
                            <h3>🔐 Acción Requerida</h3>
                            <p><strong>Necesitas cambiar tu contraseña en tu próximo inicio de sesión por razones de seguridad.</strong></p>
                        </div>

                        <p>Este cambio es obligatorio y se te solicitará automáticamente cuando inicies sesión en el sistema.</p>

                        <h3>🛡️ Para tu seguridad, asegúrate de:</h3>
                        <ul>
                            <li>Usar una contraseña única y segura</li>
                            <li>Incluir mayúsculas, minúsculas, números y símbolos</li>
                            <li>No reutilizar contraseñas de otras cuentas</li>
                            <li>Mantener tu contraseña confidencial</li>
                        </ul>

                        <div style="text-align: center; margin: 30px 0;">
                            <a href="https://gp-frontend-ebon.vercel.app/login" class="button">🔑 Iniciar Sesión</a>
                        </div>

                        <p>Si tienes dudas o necesitas asistencia, contacta a tu administrador del sistema.</p>
                    </div>
                    <div class="footer">
                        <p>Este es un mensaje automático del Sistema PMIS</p>
                        <p>Por favor, no respondas a este correo</p>
                    </div>
                </div>
            </body>
            </html>
            """

            text_content = f"""
            Cambio de Contraseña Requerido

            Hola {name or 'Usuario'},

            🔐 ACCIÓN REQUERIDA:
            Necesitas cambiar tu contraseña en tu próximo inicio de sesión por razones de seguridad.

            Este cambio es obligatorio y se te solicitará automáticamente cuando inicies sesión en el sistema.

            🛡️ PARA TU SEGURIDAD, ASEGÚRATE DE:
            - Usar una contraseña única y segura
            - Incluir mayúsculas, minúsculas, números y símbolos
            - No reutilizar contraseñas de otras cuentas
            - Mantener tu contraseña confidencial

            Si tienes dudas o necesitas asistencia, contacta a tu administrador del sistema.

            ---
            Este es un mensaje automático del Sistema PMIS
            Por favor, no respondas a este correo
            """

            return await self._send_email(
                to_email=email,
                subject="🔄 Cambio de Contraseña Requerido - Sistema PMIS",
                html_content=html_content,
                text_content=text_content,
            )

        except Exception as e:
            logger.error(f"Error in reset notification: {e}")
            return False

    async def send_notification_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        notification_type: str = "general",
        user_name: str = ""
    ) -> bool:
        """
        Enviar email de notificación general usando SMTP directo
        """
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{subject}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; }}
                    .header {{ background: #007bff; color: white; padding: 30px 20px; text-align: center; }}
                    .content {{ padding: 30px 20px; background: #f8f9fa; }}
                    .message {{ background: white; padding: 20px; margin: 20px 0; border-left: 4px solid #007bff; border-radius: 4px; }}
                    .footer {{ background: #343a40; color: white; padding: 20px; text-align: center; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📢 Sistema PMIS</h1>
                        <p>Notificación del Sistema</p>
                    </div>
                    <div class="content">
                        <p>Hola {user_name or 'Usuario'},</p>
                        <div class="message">
                            <h3>{subject}</h3>
                            {message}
                        </div>
                    </div>
                    <div class="footer">
                        <p>Este es un mensaje automático del Sistema PMIS</p>
                        <p>Por favor, no respondas a este correo</p>
                    </div>
                </div>
            </body>
            </html>
            """

            text_content = f"""
            Sistema PMIS - Notificación

            Hola {user_name or 'Usuario'},

            {subject}

            {message}

            ---
            Este es un mensaje automático del Sistema PMIS
            Por favor, no respondas a este correo
            """

            return await self._send_email(
                to_email=to_email,
                subject=f"📢 {subject} - Sistema PMIS",
                html_content=html_content,
                text_content=text_content,
            )

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False

    async def send_task_assignment_notification(
        self,
        employee_email: str,
        employee_name: str,
        task_title: str,
        task_description: str,
        due_date: str,
        priority: str,
        project_name: str = "",
    ) -> bool:
        """Notificar al empleado que le fue asignada una tarea (RF24)"""
        priority_labels = {"low": "Baja", "medium": "Media", "high": "Alta", "urgent": "Urgente"}
        priority_label = priority_labels.get(priority, priority)
        try:
            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8">
            <style>
                body{{font-family:Arial,sans-serif;color:#333;margin:0;padding:20px;}}
                .container{{max-width:600px;margin:0 auto;background:#fff;}}
                .header{{background:#2563eb;color:white;padding:28px 24px;text-align:center;}}
                .content{{padding:28px 24px;background:#f8f9fa;}}
                .card{{background:white;padding:20px;border-left:4px solid #2563eb;border-radius:6px;margin:16px 0;}}
                .footer{{background:#1f2937;color:#9ca3af;padding:20px;text-align:center;font-size:13px;}}
            </style></head><body>
            <div class="container">
                <div class="header"><h2>📋 ProjeGest — PMIS</h2><p>Nueva tarea asignada</p></div>
                <div class="content">
                    <p>Hola <strong>{employee_name}</strong>,</p>
                    <p>Se te ha asignado una nueva tarea en el sistema:</p>
                    <div class="card">
                        <h3 style="margin:0 0 8px">{task_title}</h3>
                        {"<p>" + task_description + "</p>" if task_description else ""}
                        <p><strong>Proyecto:</strong> {project_name or "—"}</p>
                        <p><strong>Fecha límite:</strong> {due_date or "Sin fecha"}</p>
                        <p><strong>Prioridad:</strong> {priority_label}</p>
                    </div>
                    <p>Ingresa al sistema para ver los detalles.</p>
                </div>
                <div class="footer"><p>Mensaje automático — Sistema PMIS · No respondas este correo</p></div>
            </div></body></html>"""
            text_content = (
                f"ProjeGest PMIS\n\nHola {employee_name},\n\n"
                f"Se te asignó la tarea: {task_title}\n"
                f"Proyecto: {project_name or '—'}\nFecha límite: {due_date or 'Sin fecha'}\n"
                f"Prioridad: {priority_label}\n\nIngresa al sistema para más detalles."
            )
            return await self._send_email(
                to_email=employee_email,
                subject=f"📋 Nueva tarea — {task_title} · PMIS",
                html_content=html_content,
                text_content=text_content,
            )
        except Exception as e:
            logger.error(f"Error enviando notificación de tarea: {e}")
            return False

    async def send_payroll_processed_notification(
        self,
        employee_email: str,
        employee_name: str,
        period_start: str,
        period_end: str,
        net_pay: float,
        receipt_url: str = "",
    ) -> bool:
        """Notificar al empleado que su nómina fue procesada (RF24)"""
        net_pay_fmt = f"${net_pay:,.0f} COP".replace(",", ".")
        try:
            receipt_link = (
                f'<p><a href="{receipt_url}" style="color:#0f766e">Ver comprobante de pago →</a></p>'
                if receipt_url else ""
            )
            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8">
            <style>
                body{{font-family:Arial,sans-serif;color:#333;margin:0;padding:20px;}}
                .container{{max-width:600px;margin:0 auto;background:#fff;}}
                .header{{background:#0f766e;color:white;padding:28px 24px;text-align:center;}}
                .content{{padding:28px 24px;background:#f8f9fa;}}
                .card{{background:white;padding:20px;border-left:4px solid #0f766e;border-radius:6px;margin:16px 0;}}
                .amount{{font-size:2rem;font-weight:700;color:#0f766e;}}
                .footer{{background:#1f2937;color:#9ca3af;padding:20px;text-align:center;font-size:13px;}}
            </style></head><body>
            <div class="container">
                <div class="header"><h2>💰 ProjeGest — PMIS</h2><p>Comprobante de nómina</p></div>
                <div class="content">
                    <p>Hola <strong>{employee_name}</strong>,</p>
                    <p>Tu pago de nómina ha sido procesado:</p>
                    <div class="card">
                        <p><strong>Período:</strong> {period_start} al {period_end}</p>
                        <p>Neto a recibir:</p>
                        <p class="amount">{net_pay_fmt}</p>
                        {receipt_link}
                    </div>
                </div>
                <div class="footer"><p>Mensaje automático — Sistema PMIS · No respondas este correo</p></div>
            </div></body></html>"""
            text_content = (
                f"ProjeGest PMIS\n\nHola {employee_name},\n\n"
                f"Tu nómina del período {period_start} al {period_end} fue procesada.\n"
                f"Neto a recibir: {net_pay_fmt}\n"
                + (f"Comprobante: {receipt_url}\n" if receipt_url else "")
            )
            return await self._send_email(
                to_email=employee_email,
                subject=f"💰 Nómina procesada — {period_start} · PMIS",
                html_content=html_content,
                text_content=text_content,
            )
        except Exception as e:
            logger.error(f"Error enviando notificación de nómina: {e}")
            return False

    async def send_cv_upload_notification(
        self,
        manager_email: str,
        manager_name: str,
        employee_name: str,
        employee_id: int,
    ) -> bool:
        """
        Notificar al gerente que un empleado subió su hoja de vida (RF05)
        """
        try:
            subject = f"Nueva hoja de vida — {employee_name}"
            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8">
            <style>
                body{{font-family:Arial,sans-serif;color:#333;margin:0;padding:20px;}}
                .container{{max-width:600px;margin:0 auto;background:#fff;}}
                .header{{background:#0f766e;color:white;padding:28px 24px;text-align:center;}}
                .content{{padding:28px 24px;background:#f8f9fa;}}
                .card{{background:white;padding:20px;border-left:4px solid #0f766e;border-radius:6px;margin:16px 0;}}
                .footer{{background:#1f2937;color:#9ca3af;padding:20px;text-align:center;font-size:13px;}}
            </style></head><body>
            <div class="container">
                <div class="header"><h2>📄 ProjeGest — PMIS</h2><p>Notificación de hoja de vida</p></div>
                <div class="content">
                    <p>Hola <strong>{manager_name}</strong>,</p>
                    <div class="card">
                        <p>El empleado <strong>{employee_name}</strong> ha actualizado su hoja de vida en el sistema.</p>
                        <p>Puedes revisarla accediendo al perfil del empleado (ID #{employee_id}) en el módulo <strong>Equipo</strong>.</p>
                    </div>
                </div>
                <div class="footer"><p>Mensaje automático — Sistema PMIS · No respondas este correo</p></div>
            </div></body></html>"""

            text_content = (
                f"ProjeGest PMIS\n\nHola {manager_name},\n\n"
                f"El empleado {employee_name} (ID #{employee_id}) ha actualizado su hoja de vida.\n"
                "Revísala en el módulo Equipo del sistema.\n\n"
                "--- Mensaje automático, no respondas este correo ---"
            )

            return await self._send_email(
                to_email=manager_email,
                subject=f"📄 Nueva hoja de vida — {employee_name} · PMIS",
                html_content=html_content,
                text_content=text_content,
            )
        except Exception as e:
            logger.error(f"Error enviando notificación de CV: {e}")
            return False

    async def send_employee_report_email(
        self,
        employee_email: str,
        employee_name: str,
        pdf_bytes: bytes,
        employee_id: int,
    ) -> bool:
        """
        Enviar informe de desempeño PDF al empleado/gerente por correo (RF16).
        """
        from datetime import date
        report_date = date.today().strftime('%d/%m/%Y')
        filename = f"informe_desempeno_{employee_id}_{date.today().isoformat()}.pdf"
        try:
            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8">
            <style>
                body{{font-family:Arial,sans-serif;color:#333;margin:0;padding:20px;}}
                .container{{max-width:600px;margin:0 auto;background:#fff;}}
                .header{{background:#003C68;color:white;padding:28px 24px;text-align:center;}}
                .content{{padding:28px 24px;background:#f8f9fa;}}
                .card{{background:white;padding:20px;border-left:4px solid #003C68;border-radius:6px;margin:16px 0;}}
                .footer{{background:#1f2937;color:#9ca3af;padding:20px;text-align:center;font-size:13px;}}
            </style></head><body>
            <div class="container">
                <div class="header"><h2>📊 ProjeGest — PMIS</h2><p>Informe de Desempeño</p></div>
                <div class="content">
                    <p>Estimado/a <strong>{employee_name}</strong>,</p>
                    <div class="card">
                        <p>Adjunto encontrarás tu <strong>informe de desempeño</strong> generado el <strong>{report_date}</strong>.</p>
                        <p>El documento incluye métricas de tareas completadas, proyectos asignados y tasa de cumplimiento.</p>
                    </div>
                    <p>Si tienes preguntas sobre tu informe, contáctate con tu gerente.</p>
                </div>
                <div class="footer"><p>Mensaje automático — Sistema PMIS · No respondas este correo</p></div>
            </div></body></html>"""
            text_content = (
                f"ProjeGest PMIS — Informe de Desempeño\n\n"
                f"Estimado/a {employee_name},\n\n"
                f"Adjunto encontrarás tu informe de desempeño generado el {report_date}.\n"
                "El documento incluye métricas de tareas completadas, proyectos asignados y tasa de cumplimiento.\n\n"
                "Si tienes preguntas, contáctate con tu gerente.\n\n"
                "--- Mensaje automático, no respondas este correo ---"
            )
            return await self._send_email_with_attachment(
                to_email=employee_email,
                subject=f"📊 Informe de desempeño — {employee_name} · {report_date}",
                html_content=html_content,
                text_content=text_content,
                attachments=[(filename, pdf_bytes, "application/pdf")],
            )
        except Exception as e:
            logger.error(f"Error enviando informe por email: {e}")
            return False

    def validate_password_strength(self, password: str) -> dict:
        """
        Validar fortaleza de contraseña según políticas de empresa
        """
        validations = {
            'length': len(password) >= 8,
            'has_uppercase': any(c.isupper() for c in password),
            'has_lowercase': any(c.islower() for c in password),
            'has_digit': any(c.isdigit() for c in password),
            'has_symbol': any(c in '@#$%&*+-=?!()[]{}|:;,.<>/' for c in password)
        }

        score = sum(validations.values())
        strength = 'weak' if score < 3 else 'medium' if score < 5 else 'strong'

        return {
            'is_valid': score >= 4,  # Al menos 4 de 5 criterios
            'strength': strength,
            'score': score,
            'validations': validations,
            'suggestions': self._get_password_suggestions(validations)
        }

    def _get_password_suggestions(self, validations: dict) -> list:
        """Generar sugerencias para mejorar contraseña"""
        suggestions = []
        if not validations['length']:
            suggestions.append("Usa al menos 8 caracteres")
        if not validations['has_uppercase']:
            suggestions.append("Incluye al menos una letra mayúscula")
        if not validations['has_lowercase']:
            suggestions.append("Incluye al menos una letra minúscula")
        if not validations['has_digit']:
            suggestions.append("Incluye al menos un número")
        if not validations['has_symbol']:
            suggestions.append("Incluye al menos un símbolo (@#$%&*+-=?)")

        return suggestions

# Instancia global del servicio
notification_service = NotificationService()