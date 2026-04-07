import logging
from typing import Optional
from app.database import supabase

logger = logging.getLogger(__name__)

class EmailService:
    async def send_project_assignment_notification(self, user_id: str, project_name: str):
        """Enviar notificación de asignación a proyecto por email"""
        try:
            # Obtener información del usuario
            user_response = supabase.table("users").select("email").eq("id", user_id).execute()
            if not user_response.data:
                logger.error(f"Usuario {user_id} no encontrado para envío de email")
                return

            user_email = user_response.data[0]['email']

            # Preparar datos del email
            email_data = {
                "to_email": user_email,
                "subject": f"Asignación a proyecto: {project_name}",
                "html_content": f"""
                <h2>Asignación a Proyecto</h2>
                <p>Has sido asignado al proyecto: <strong>{project_name}</strong></p>
                <p>Puedes ver los detalles del proyecto en tu dashboard.</p>
                """,
                "text_content": f"Has sido asignado al proyecto: {project_name}",
                "email_type": "project_assignment",
                "metadata": {
                    "user_id": user_id,
                    "project_name": project_name
                }
            }

            # Insertar en la cola de emails
            response = supabase.table("email_queue").insert(email_data).execute()

            if response.data:
                logger.info(f"Email de asignación de proyecto encolado para {user_email}")
            else:
                logger.error(f"Error encolando email para {user_email}")

        except Exception as e:
            logger.error(f"Error enviando notificación de asignación: {e}")

email_service = EmailService()