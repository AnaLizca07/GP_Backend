from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime, date
from decimal import Decimal
import uuid

# Enumeraciones para estados de proyecto
class ProjectStatus(str):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# Modelos de Request
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    budget: Optional[Decimal] = Field(None, gt=0)
    sponsor_id: Optional[str] = None

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and 'start_date' in values and v <= values['start_date']:
            raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

    @validator('budget')
    def validate_budget(cls, v):
        if v is not None and v <= 0:
            raise ValueError('El presupuesto debe ser mayor a 0')
        return v

    @validator('sponsor_id')
    def validate_sponsor_id(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        try:
            # Validar que sea un UUID válido
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('El sponsor_id debe ser un UUID válido')
        except TypeError:
            raise ValueError('El sponsor_id debe ser una cadena UUID válida')

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = Field(None, gt=0)
    status: Optional[Literal["planning", "active", "on_hold", "completed", "cancelled"]] = None
    sponsor_id: Optional[str] = None

    @validator('budget')
    def validate_budget(cls, v):
        if v is not None and v <= 0:
            raise ValueError('El presupuesto debe ser mayor a 0')
        return v

    @validator('sponsor_id')
    def validate_sponsor_id(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        try:
            # Validar que sea un UUID válido
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('El sponsor_id debe ser un UUID válido')
        except TypeError:
            raise ValueError('El sponsor_id debe ser una cadena UUID válida')

class ProjectEmployeeAssign(BaseModel):
    employee_id: int
    dedication_percentage: Decimal = Field(..., gt=0, le=100)

# Modelos de Response
class ProjectEmployeeResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_position: Optional[str]
    employee_phone: Optional[str] = None
    employee_identification: Optional[str] = None
    dedication_percentage: Decimal
    assigned_at: datetime

class ProjectResponse(BaseModel):
    id: int
    code: Optional[str] = None   # RF06: código único generado
    name: str
    description: Optional[str]
    start_date: date
    end_date: Optional[date]
    budget: Optional[Decimal]
    status: str
    sponsor_id: Optional[str]
    sponsor_email: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    assigned_employees: List[ProjectEmployeeResponse] = []

class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
    page: int
    limit: int

class ProjectStatsResponse(BaseModel):
    total_projects: int
    active_projects: int
    completed_projects: int
    total_budget: Decimal
    spent_budget: Decimal
    employees_assigned: int