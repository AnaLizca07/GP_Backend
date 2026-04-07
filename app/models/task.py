from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime, date

VALID_STATUSES = ['pending', 'in_progress', 'completed', 'blocked']
VALID_PRIORITIES = ['low', 'medium', 'high', 'urgent']


class TaskCreate(BaseModel):
    project_id: int
    employee_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = 'pending'
    priority: str = 'medium'
    due_date: Optional[date] = None

    @validator('status')
    def validate_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f'Estado debe ser uno de: {VALID_STATUSES}')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v not in VALID_PRIORITIES:
            raise ValueError(f'Prioridad debe ser una de: {VALID_PRIORITIES}')
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    employee_id: Optional[int] = None

    @validator('status')
    def validate_status(cls, v):
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f'Estado debe ser uno de: {VALID_STATUSES}')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in VALID_PRIORITIES:
            raise ValueError(f'Prioridad debe ser una de: {VALID_PRIORITIES}')
        return v


class TaskStatusUpdate(BaseModel):
    status: str

    @validator('status')
    def validate_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f'Estado debe ser uno de: {VALID_STATUSES}')
        return v


class TaskDeliverableResponse(BaseModel):
    id: int
    task_id: int
    file_name: str
    file_url: str
    file_size: int
    uploaded_at: datetime


class TaskResponse(BaseModel):
    id: int
    code: Optional[str] = None   # RF10: código único generado
    project_id: int
    project_name: str
    employee_id: Optional[int]
    employee_name: Optional[str]
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[date]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    deliverables: List[TaskDeliverableResponse] = []


class TaskStatusResponse(BaseModel):
    id: int
    status: str
    completed_at: Optional[datetime]


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
