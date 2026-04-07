from typing import Optional
from app.database import get_admin_supabase


class RatingsService:

    def _sb(self):
        return get_admin_supabase()

    async def create_rating(
        self,
        employee_id: int,
        stars: int,
        comment: Optional[str],
        rated_by: str,
    ) -> dict:
        sb = self._sb()
        result = sb.table("employee_ratings").insert({
            "employee_id": employee_id,
            "rated_by": rated_by,
            "stars": stars,
            "comment": comment or None,
        }).execute()
        if not result.data:
            raise Exception("No se pudo guardar la calificación")
        return result.data[0]

    async def get_ratings(self, employee_id: int) -> list[dict]:
        sb = self._sb()
        result = (
            sb.table("employee_ratings")
            .select("id, stars, comment, created_at, users(id, email)")
            .eq("employee_id", employee_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data or []
        return [
            {
                "id": r["id"],
                "stars": r["stars"],
                "comment": r["comment"],
                "created_at": r["created_at"],
                "rated_by_email": (r.get("users") or {}).get("email"),
            }
            for r in rows
        ]


ratings_service = RatingsService()
