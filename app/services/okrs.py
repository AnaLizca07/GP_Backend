import logging
from typing import Optional, List
from datetime import date

from app.database import get_admin_supabase

logger = logging.getLogger(__name__)


def _supabase():
    return get_admin_supabase()


class OkrService:

    async def get_okrs(
        self,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> List[dict]:
        try:
            sb = _supabase()
            query = sb.table("okrs").select(
                "id, title, description, progress, project_id, target_date, status, created_by, created_at, updated_at, projects(id, name)"
            ).order("created_at", desc=True)

            if project_id is not None:
                query = query.eq("project_id", project_id)
            if status:
                query = query.eq("status", status)

            res = query.execute()
            result = []
            for row in res.data or []:
                proj = row.pop("projects", None) or {}
                row["project_name"] = proj.get("name")
                result.append(row)
            return result
        except Exception as e:
            logger.error(f"Error en get_okrs: {e}")
            raise

    async def get_okr(self, okr_id: int) -> Optional[dict]:
        try:
            sb = _supabase()
            res = (
                sb.table("okrs")
                .select("id, title, description, progress, project_id, target_date, status, created_by, created_at, updated_at, projects(id, name)")
                .eq("id", okr_id)
                .execute()
            )
            if not res.data:
                return None
            row = res.data[0]
            proj = row.pop("projects", None) or {}
            row["project_name"] = proj.get("name")
            return row
        except Exception as e:
            logger.error(f"Error en get_okr({okr_id}): {e}")
            raise

    async def create_okr(self, data: dict) -> dict:
        try:
            sb = _supabase()
            payload = {
                "title": data["title"],
                "description": data.get("description"),
                "progress": data.get("progress", 0),
                "project_id": data.get("project_id"),
                "target_date": data.get("target_date"),
                "status": data.get("status", "active"),
                "created_by": data.get("created_by"),
            }
            res = sb.table("okrs").insert(payload).execute()
            if not res.data:
                raise ValueError("No se pudo crear el OKR")
            created = res.data[0]
            return await self.get_okr(created["id"]) or created
        except Exception as e:
            logger.error(f"Error en create_okr: {e}")
            raise

    async def update_okr(self, okr_id: int, data: dict) -> Optional[dict]:
        try:
            sb = _supabase()
            # Verify exists
            existing = await self.get_okr(okr_id)
            if not existing:
                return None

            payload = {}
            for field in ("title", "description", "progress", "project_id", "target_date", "status"):
                if field in data and data[field] is not None:
                    payload[field] = data[field]
            # Allow explicit None for nullable fields
            for field in ("description", "project_id", "target_date"):
                if field in data:
                    payload[field] = data[field]

            if not payload:
                return existing

            res = sb.table("okrs").update(payload).eq("id", okr_id).execute()
            if not res.data:
                return None
            return await self.get_okr(okr_id)
        except Exception as e:
            logger.error(f"Error en update_okr({okr_id}): {e}")
            raise

    async def delete_okr(self, okr_id: int) -> bool:
        try:
            sb = _supabase()
            existing = await self.get_okr(okr_id)
            if not existing:
                return False
            sb.table("okrs").delete().eq("id", okr_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error en delete_okr({okr_id}): {e}")
            raise


okr_service = OkrService()
