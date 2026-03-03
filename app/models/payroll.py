from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, Dict, Any, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

class EmployeeType(str, Enum):
    EMPLOYEE = "employee"  # Empleado dependiente
    CONTRACTOR = "contractor"  # Contratista por prestación de servicios

class PayPeriod(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"

class RiskLevel(str, Enum):
    LEVEL_I = "I"    # Riesgo mínimo - 0.522%
    LEVEL_II = "II"  # Riesgo bajo - 1.044%
    LEVEL_III = "III" # Riesgo medio - 2.436%
    LEVEL_IV = "IV"   # Riesgo alto - 4.35%
    LEVEL_V = "V"     # Riesgo máximo - 6.96%

class SocialSecurityConfig(BaseModel):
    """Configuración de parafiscales y seguridad social"""
    health_employee: float = Field(default=4.0, description="Salud empleado (%)")
    health_employer: float = Field(default=8.5, description="Salud empleador (%)")
    pension_employee: float = Field(default=4.0, description="Pensión empleado (%)")
    pension_employer: float = Field(default=12.0, description="Pensión empleador (%)")
    solidarity_fund: float = Field(default=1.0, description="Fondo solidaridad pensional (%) - para salarios > 4 SMLV")
    family_compensation: float = Field(default=4.0, description="Caja compensación familiar (%)")
    icbf: float = Field(default=3.0, description="ICBF (%)")
    sena: float = Field(default=2.0, description="SENA (%)")

    # ARL por nivel de riesgo
    arl_rates: Dict[str, float] = Field(default={
        "I": 0.522,
        "II": 1.044,
        "III": 2.436,
        "IV": 4.35,
        "V": 6.96
    }, description="Tasas ARL por nivel de riesgo (%)")

    # Parafiscales para contratistas
    contractor_health: float = Field(default=12.5, description="Salud contratista sobre 40% de honorarios (%)")
    contractor_pension: float = Field(default=16.0, description="Pensión contratista sobre 40% de honorarios (%)")
    contractor_base_percentage: float = Field(default=40.0, description="% de honorarios para calcular seguridad social contratistas")

class PayrollCalculationRequest(BaseModel):
    """Request para calcular nómina"""
    employee_id: int
    pay_period: PayPeriod
    period_start: date
    period_end: date
    worked_hours: Optional[float] = None  # Para empleados por horas
    base_salary: Optional[float] = None   # Override del salario base
    additional_income: Optional[float] = Field(default=0, description="Ingresos adicionales")
    deductions: Optional[float] = Field(default=0, description="Deducciones especiales")
    risk_level: RiskLevel = Field(default=RiskLevel.LEVEL_I, description="Nivel de riesgo para ARL")

    @validator('worked_hours')
    def validate_worked_hours(cls, v, values):
        if v is not None and v < 0:
            raise ValueError('Las horas trabajadas no pueden ser negativas')
        return v

    @validator('additional_income', 'deductions')
    def validate_amounts(cls, v):
        if v < 0:
            raise ValueError('Los montos no pueden ser negativos')
        return v

class SocialSecurityDeductions(BaseModel):
    """Deducciones de seguridad social empleado"""
    health: float = Field(description="Deducción salud")
    pension: float = Field(description="Deducción pensión")
    solidarity_fund: float = Field(default=0, description="Fondo solidaridad pensional")
    total: float = Field(description="Total deducciones empleado")

class EmployerContributions(BaseModel):
    """Aportes del empleador"""
    health: float = Field(description="Aporte salud")
    pension: float = Field(description="Aporte pensión")
    arl: float = Field(description="ARL")
    family_compensation: float = Field(description="Caja compensación")
    icbf: float = Field(description="ICBF")
    sena: float = Field(description="SENA")
    total: float = Field(description="Total aportes empleador")

class BenefitsCalculation(BaseModel):
    """Cálculo de prestaciones sociales"""
    vacation_days: float = Field(description="Días de vacaciones acumulados")
    vacation_amount: float = Field(description="Valor vacaciones")
    severance: float = Field(description="Cesantías")
    severance_interest: float = Field(description="Intereses sobre cesantías")
    service_bonus: float = Field(description="Prima de servicios")
    total_benefits: float = Field(description="Total prestaciones")

class ContractorCalculation(BaseModel):
    """Cálculo para contratistas"""
    fees_total: float = Field(description="Total honorarios")
    taxable_base: float = Field(description="Base gravable (40% de honorarios)")
    health_contribution: float = Field(description="Aporte salud")
    pension_contribution: float = Field(description="Aporte pensión")
    total_contributions: float = Field(description="Total aportes")
    net_amount: float = Field(description="Valor neto a recibir")

class PayrollCalculationResult(BaseModel):
    """Resultado del cálculo de nómina"""
    employee_id: int
    employee_name: str
    employee_identification: str
    employee_type: EmployeeType
    pay_period: PayPeriod
    period_start: date
    period_end: date

    # Salarios base
    base_salary: float = Field(description="Salario base del período")
    worked_hours: Optional[float] = Field(description="Horas trabajadas")
    hourly_rate: Optional[float] = Field(description="Tarifa por hora")

    # Ingresos
    additional_income: float = Field(description="Ingresos adicionales")
    gross_income: float = Field(description="Ingreso bruto")

    # Deducciones y aportes
    social_security_deductions: SocialSecurityDeductions
    employer_contributions: EmployerContributions
    special_deductions: float = Field(description="Deducciones especiales")

    # Prestaciones (solo empleados)
    benefits: Optional[BenefitsCalculation] = None

    # Contratistas
    contractor_calculation: Optional[ContractorCalculation] = None

    # Totales
    total_deductions: float = Field(description="Total deducciones")
    net_salary: float = Field(description="Salario neto")
    employer_cost: float = Field(description="Costo total para empleador")

    # Metadatos
    calculation_date: datetime = Field(default_factory=datetime.now)
    risk_level: RiskLevel
    current_minimum_wage: float = Field(description="Salario mínimo vigente")

    class Config:
        json_encoders = {
            Decimal: float,
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }

class PayrollRecord(BaseModel):
    """Registro de nómina procesada - compatible con tabla payroll de BD"""
    id: Optional[int] = None
    employee_id: int
    period_start: date
    period_end: date
    base_salary: float
    deductions: Dict[str, float] = Field(description="Deducciones en formato JSON")
    employer_contributions: Dict[str, float] = Field(description="Aportes patronales en formato JSON")
    benefits: Dict[str, float] = Field(description="Prestaciones sociales en formato JSON")
    bonuses: List[Dict[str, Any]] = Field(default=[], description="Bonificaciones extras")
    net_pay: float
    status: Literal["pending", "processed", "paid"] = "pending"
    receipt_url: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    processed_by: Optional[str] = None

class PayrollRecordCreate(BaseModel):
    """Crear registro de nómina"""
    employee_id: int
    calculation_result: PayrollCalculationResult

class PayrollRecordResponse(BaseModel):
    """Response de registro de nómina"""
    id: int
    employee_id: int
    employee_name: str
    period_start: date
    period_end: date
    base_salary: float
    deductions: Dict[str, float]
    employer_contributions: Dict[str, float]
    benefits: Dict[str, float]
    net_pay: float
    status: str
    receipt_url: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None

class PayrollSummary(BaseModel):
    """Resumen de nómina por período"""
    pay_period: PayPeriod
    period_start: date
    period_end: date
    total_employees: int
    total_gross: float
    total_deductions: float
    total_net: float
    total_employer_cost: float
    by_employee_type: Dict[str, Dict[str, float]]

class MinimumWageConfig(BaseModel):
    """Configuración del salario mínimo"""
    year: int
    monthly_amount: float
    daily_amount: float
    hourly_amount: float
    transportation_allowance: float
    effective_date: date