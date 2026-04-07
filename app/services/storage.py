"""
Servicio para manejo de archivos en Supabase Storage
"""
import os
import uuid
import magic
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile
from supabase import Client
from app.config import settings
from app.database import supabase

class StorageService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    async def upload_resume(self, file: UploadFile, employee_id: int) -> str:
        """
        Sube una hoja de vida (PDF) a Supabase Storage

        Args:
            file: Archivo PDF subido
            employee_id: ID del empleado

        Returns:
            URL pública del archivo en Supabase Storage

        Raises:
            HTTPException: Si hay errores en la validación o subida
        """
        # Validar que es un archivo PDF
        await self._validate_pdf_file(file)

        # Generar nombre único para el archivo
        file_extension = self._get_file_extension(file.filename)
        unique_filename = f"employee_{employee_id}_{uuid.uuid4()}{file_extension}"

        try:
            # Leer contenido del archivo
            file_content = await file.read()

            # Subir archivo a Supabase Storage
            response = self.supabase.storage.from_("resumes").upload(
                file=file_content,
                path=unique_filename,
                file_options={
                    "content-type": file.content_type or "application/pdf"
                }
            )

            if response.path:
                # Obtener URL pública del archivo
                public_url = self.supabase.storage.from_("resumes").get_public_url(unique_filename)
                return public_url
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Error al subir el archivo a Supabase Storage"
                )

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=500,
                detail=f"Error interno al procesar el archivo: {str(e)}"
            )

    async def delete_resume(self, file_url: str) -> bool:
        """
        Elimina una hoja de vida de Supabase Storage

        Args:
            file_url: URL del archivo a eliminar

        Returns:
            True si se eliminó exitosamente, False en caso contrario
        """
        try:
            # Extraer el nombre del archivo de la URL
            filename = self._extract_filename_from_url(file_url)

            if filename:
                response = self.supabase.storage.from_("resumes").remove([filename])
                return len(response) > 0
            return False

        except Exception:
            return False

    async def _validate_pdf_file(self, file: UploadFile) -> None:
        """
        Valida que el archivo sea un PDF válido

        Args:
            file: Archivo a validar

        Raises:
            HTTPException: Si el archivo no es válido
        """
        # Validar extensión
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nombre de archivo requerido")

        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Solo se permiten archivos PDF"
            )

        # Validar tamaño (máximo 5MB — RF05)
        if file.size and file.size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(
                status_code=400,
                detail="El archivo no puede exceder 5MB"
            )

        # Validar tipo MIME
        file_content = await file.read()
        await file.seek(0)  # Regresar al inicio para uso posterior

        try:
            mime_type = magic.from_buffer(file_content, mime=True)
            if mime_type != 'application/pdf':
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipo de archivo no válido. Se esperaba PDF, se recibió {mime_type}"
                )
        except Exception:
            # Si no se puede determinar el tipo MIME, al menos validar la extensión
            pass

    def _get_file_extension(self, filename: Optional[str]) -> str:
        """
        Obtiene la extensión del archivo

        Args:
            filename: Nombre del archivo

        Returns:
            Extensión del archivo (ej: '.pdf')
        """
        if not filename:
            return '.pdf'
        return os.path.splitext(filename)[1].lower() or '.pdf'

    def _extract_filename_from_url(self, file_url: str) -> Optional[str]:
        """
        Extrae el nombre del archivo de una URL de Supabase Storage

        Args:
            file_url: URL del archivo

        Returns:
            Nombre del archivo o None si no se puede extraer
        """
        try:
            # Buscar el patrón /storage/v1/object/public/resumes/
            bucket_path = "/storage/v1/object/public/resumes/"
            if bucket_path in file_url:
                return file_url.split(bucket_path)[-1]
            return None
        except Exception:
            return None

# Función de utilidad para obtener una instancia del servicio
def get_storage_service() -> StorageService:
    """
    Obtiene una instancia del servicio de storage

    Returns:
        Instancia de StorageService
    """
    return StorageService(supabase)