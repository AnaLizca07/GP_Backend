import secrets
import string
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        # Configuración SMTP desde variables de entorno
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        # Limpiar espacios de la contraseña (las contraseñas de aplicación de Gmail a veces tienen espacios)
        self.smtp_password = os.getenv('SMTP_PASSWORD').replace(' ', '') if os.getenv('SMTP_PASSWORD') else None
        self.smtp_from_email = os.getenv('SMTP_FROM_EMAIL', self.smtp_user)
        self.smtp_from_name = os.getenv('SMTP_FROM_NAME', 'Sistema PMIS')
        self.use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

        # Validar que las credenciales SMTP están configuradas
        invalid_placeholders = ['tu-email@gmail.com', 'tu-password-de-aplicacion', 'your-email@example.com']

        if (not self.smtp_user or
            not self.smtp_password or
            self.smtp_user in invalid_placeholders or
            self.smtp_password in invalid_placeholders):
            logger.warning("SMTP not configured properly. Email notifications will be displayed in console.")
            self.smtp_configured = False
        else:
            self.smtp_configured = True
            logger.info(f"SMTP configured successfully for {self.smtp_user[:3]}***@***")

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

    def _send_smtp_email(self, to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        """
        Enviar email usando configuración SMTP directa
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
            msg['To'] = to_email

            # Agregar contenido texto plano
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(text_part)

            # Agregar contenido HTML
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # Conectar y enviar
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error sending SMTP email: {e}")
            return False

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
                            <a href="#" class="button">🚀 Acceder al Sistema</a>
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

            # Enviar email usando SMTP
            success = self._send_smtp_email(
                to_email=email,
                subject="🎉 ¡Bienvenido al Sistema PMIS! - Credenciales de Acceso",
                html_content=html_content,
                text_content=text_content
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
                            <a href="#" class="button">🔑 Iniciar Sesión</a>
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

            return self._send_smtp_email(
                to_email=email,
                subject="🔄 Cambio de Contraseña Requerido - Sistema PMIS",
                html_content=html_content,
                text_content=text_content
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

            return self._send_smtp_email(
                to_email=to_email,
                subject=f"📢 {subject} - Sistema PMIS",
                html_content=html_content,
                text_content=text_content
            )

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
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