from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, Literal, List
from pydantic import BaseModel, Field

from app.models.auth import UserResponse
from app.database import get_admin_supabase

from app.api.deps import get_current_user, require_manager

router = APIRouter(prefix="/finance", tags=["finance"])
supabase = get_admin_supabase()


def _require_project_exists(user_id: str) -> None:
    """Lanza 403 si el manager no tiene ningún proyecto creado."""
    res = get_admin_supabase().table("projects").select("id").eq("created_by", user_id).limit(1).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes tener al menos un proyecto creado antes de registrar transacciones financieras.",
        )

# ── Modelos ────────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    type: Literal["income", "expense"]
    amount: float = Field(..., gt=0, description="Monto mayor a 0")
    category: str
    description: str          # concepto principal
    project_id: Optional[int] = None
    transaction_date: str     # YYYY-MM-DD

class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: float
    category: str
    description: str
    project_id: Optional[int]
    transaction_date: str
    created_at: str
    created_by: Optional[str] = None

class FinanceSummary(BaseModel):
    total_income: float
    total_expense: float
    balance: float
    income_count: int
    expense_count: int

# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt(row: dict) -> TransactionResponse:
    return TransactionResponse(
        id=row["id"],
        type=row["type"],
        amount=row["amount"],
        category=row.get("category") or "",
        description=row.get("description") or "",
        project_id=row.get("project_id"),
        transaction_date=row.get("transaction_date") or "",
        created_at=row.get("created_at") or "",
        created_by=row.get("created_by"),
    )

# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post(
    "/transactions/",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    data: TransactionCreate,
    current_user: UserResponse = Depends(require_manager),
):
    """Registrar ingreso o egreso. Acceso: solo gerentes."""
    _require_project_exists(current_user.id)
    try:
        result = supabase.table("transactions").insert({
            "type": data.type,
            "amount": data.amount,
            "category": data.category,
            "description": data.description,
            "project_id": data.project_id,
            "transaction_date": data.transaction_date,
            "created_by": current_user.id,   # ← identifica al gerente dueño
        }).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Error al crear transacción")
        return _fmt(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transactions/", response_model=List[TransactionResponse])
async def get_transactions(
    type: Optional[str] = Query(None, pattern="^(income|expense)$"),
    project_id: Optional[int] = None,
    current_user: UserResponse = Depends(require_manager),
):
    """Listar transacciones del gerente autenticado. Acceso: solo gerentes."""
    try:
        query = supabase.table("transactions").select("*").eq("created_by", current_user.id)
        if type:
            query = query.eq("type", type)
        if project_id:
            query = query.eq("project_id", project_id)
        result = query.order("transaction_date", desc=True).execute()
        return [_fmt(r) for r in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    current_user: UserResponse = Depends(require_manager),
):
    """Eliminar transacción propia. Acceso: solo gerentes."""
    # Verificar que la transacción pertenece al gerente autenticado
    check = supabase.table("transactions").select("id,created_by").eq("id", transaction_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    if check.data[0].get("created_by") not in (None, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta transacción")
    supabase.table("transactions").delete().eq("id", transaction_id).execute()

@router.get("/summary/", response_model=FinanceSummary)
async def get_summary(
    current_user: UserResponse = Depends(require_manager),
):
    """Resumen financiero del gerente autenticado: total ingresos, egresos, balance."""
    try:
        result = supabase.table("transactions").select("type,amount").eq("created_by", current_user.id).execute()
        rows = result.data or []
        total_income = sum(r["amount"] for r in rows if r["type"] == "income")
        total_expense = sum(r["amount"] for r in rows if r["type"] == "expense")
        return FinanceSummary(
            total_income=total_income,
            total_expense=total_expense,
            balance=total_income - total_expense,
            income_count=sum(1 for r in rows if r["type"] == "income"),
            expense_count=sum(1 for r in rows if r["type"] == "expense"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
