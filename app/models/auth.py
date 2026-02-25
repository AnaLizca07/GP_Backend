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

# Modelos para empleados
class EmployeeCreate(BaseModel):
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

# Modelo de error
class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None