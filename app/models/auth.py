from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    MANAGER = "manager"
    EMPLOYEE = "employee"
    SPONSOR = "sponsor"

# Modelos de Request (entrada)
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRole

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordUpdate(BaseModel):
    password: str = Field(..., min_length=6, max_length=100)

# Modelos de Response (salida)
class UserResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    created_at: datetime
    updated_at: Optional[datetime] = None
    must_change_password: Optional[bool] = False

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class TokenPayload(BaseModel):
    sub: Optional[str] = None  # user_id
    email: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[datetime] = None
    must_change_password: Optional[bool] = False

# Modelos para empleados
class EmployeeCreateComplete(BaseModel):
    """Modelo para crear empleado completo (usuario + perfil)"""
    # Datos de usuario (para Supabase Auth)
    email: EmailStr

    # Datos del perfil de empleado
    name: str = Field(..., min_length=2, max_length=255)
    identification: str = Field(..., min_length=5, max_length=50)
    position: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    salary_type: Optional[Literal["hourly", "biweekly", "monthly"]] = None
    salary_hourly: Optional[float] = Field(None, ge=0)
    salary_biweekly: Optional[float] = Field(None, ge=0)
    salary_monthly: Optional[float] = Field(None, ge=0)
    resume_url: Optional[str] = None
    status: Literal["active", "inactive"] = "active"

    @validator('email')
    def validate_institutional_email(cls, v):
        """Validar que sea email institucional (RF02)"""
        allowed_domains = ['@cue.edu.co', '@unihumboldt.edu.co']
        if not any(v.lower().endswith(domain) for domain in allowed_domains):
            raise ValueError('El correo debe ser institucional (@cue.edu.co o @unihumboldt.edu.co)')
        return v.lower()

class EmployeeCreate(BaseModel):
    """Modelo para crear solo perfil de empleado (cuando ya existe el usuario)"""
    user_id: str
    name: str = Field(..., min_length=2, max_length=255)
    identification: str = Field(..., min_length=5, max_length=50)
    position: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    salary_type: Optional[Literal["hourly", "biweekly", "monthly"]] = None
    salary_hourly: Optional[float] = Field(None, ge=0)
    salary_biweekly: Optional[float] = Field(None, ge=0)
    salary_monthly: Optional[float] = Field(None, ge=0)
    resume_url: Optional[str] = None
    status: Literal["active", "inactive"] = "active"

class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    identification: Optional[str] = Field(None, min_length=5, max_length=50)
    position: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    salary_type: Optional[Literal["hourly", "biweekly", "monthly"]] = None
    salary_hourly: Optional[float] = Field(None, ge=0)
    salary_biweekly: Optional[float] = Field(None, ge=0)
    salary_monthly: Optional[float] = Field(None, ge=0)
    resume_url: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None

class EmployeeResponse(BaseModel):
    id: int
    user_id: str
    name: str
    identification: str
    position: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    salary_type: Optional[str] = None
    salary_hourly: Optional[float] = None
    salary_biweekly: Optional[float] = None
    salary_monthly: Optional[float] = None
    resume_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

class EmployeeListResponse(BaseModel):
    employees: list[EmployeeResponse]
    total: int
    page: int
    limit: int

# Modelo de error
class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None