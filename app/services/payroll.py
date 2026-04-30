from datetime import datetime, date
from typing import Optional, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
import logging

from app.models.payroll import (
    PayrollCalculationRequest,
    PayrollCalculationResult,
    SocialSecurityDeductions,
    EmployerContributions,
    BenefitsCalculation,
    ContractorCalculation,
    SocialSecurityConfig,
    EmployeeType,
    PayPeriod,
    RiskLevel
)
from app.models.auth import EmployeeResponse
from app.models.payroll import PayrollRecord

logger = logging.getLogger(__name__)

class PayrollCalculationService:
    """Servicio para cálculos de nómina y seguridad social"""

    def __init__(self):
        # Configuración por defecto de seguridad social Colombia 2024
        self.config = SocialSecurityConfig()
        # Salario mínimo 2024 Colombia (actualizar anualmente)
        self.current_minimum_wage = 1300000  # $1,300,000 COP

    def calculate_employee_payroll(
        self,
        employee: EmployeeResponse,
        request: PayrollCalculationRequest
    ) -> PayrollCalculationResult:
        """
        Calcula nómina completa para empleado dependiente o contratista

        Args:
            employee: Datos del empleado
            request: Parámetros del cálculo

        Returns:
            PayrollCalculationResult: Resultado completo del cálculo
        """
        logger.info(f"Calculando nómina para empleado {employee.id} - período {request.period_start} a {request.period_end}")

        # Determinar tipo de empleado y salario base
        employee_type = self._determine_employee_type(employee)
        base_salary = self._calculate_base_salary(employee, request)

        # Calcular ingreso bruto
        gross_income = base_salary + request.additional_income

        if employee_type == EmployeeType.EMPLOYEE:
            return self._calculate_employee_dependent(employee, request, gross_income)
        else:
            return self._calculate_contractor(employee, request, gross_income)

    def _calculate_employee_dependent(
        self,
        employee: EmployeeResponse,
        request: PayrollCalculationRequest,
        gross_income: float
    ) -> PayrollCalculationResult:
        """Calcula nómina para empleado dependiente (contrato fijo/indefinido)"""

        # Calcular deducciones de seguridad social del empleado
        social_security_deductions = self._calculate_employee_deductions(gross_income)

        # Calcular aportes del empleador
        employer_contributions = self._calculate_employer_contributions(gross_income, request.risk_level)

        # Calcular prestaciones sociales
        benefits = self._calculate_benefits(employee, gross_income, request.pay_period)

        # Calcular totales
        total_deductions = social_security_deductions.total + request.deductions
        net_salary = gross_income - total_deductions
        employer_cost = gross_income + employer_contributions.total

        return PayrollCalculationResult(
            employee_id=employee.id,
            employee_name=employee.name,
            employee_identification=employee.identification,
            employee_type=EmployeeType.EMPLOYEE,
            pay_period=request.pay_period,
            period_start=request.period_start,
            period_end=request.period_end,
            base_salary=request.base_salary or self._get_employee_salary(employee, request.pay_period),
            worked_hours=request.worked_hours,
            hourly_rate=employee.salary_hourly,
            additional_income=request.additional_income,
            gross_income=gross_income,
            social_security_deductions=social_security_deductions,
            employer_contributions=employer_contributions,
            special_deductions=request.deductions,
            benefits=benefits,
            total_deductions=total_deductions,
            net_salary=net_salary,
            employer_cost=employer_cost,
            risk_level=request.risk_level,
            current_minimum_wage=self.current_minimum_wage
        )

    def _calculate_contractor(
        self,
        employee: EmployeeResponse,
        request: PayrollCalculationRequest,
        gross_income: float
    ) -> PayrollCalculationResult:
        """Calcula para contratista por prestación de servicios"""

        # Base para cálculo: 40% de los honorarios
        taxable_base = gross_income * (self.config.contractor_base_percentage / 100)

        # Calcular aportes del contratista
        health_contribution = self._round_currency(taxable_base * (self.config.contractor_health / 100))
        pension_contribution = self._round_currency(taxable_base * (self.config.contractor_pension / 100))
        total_contributions = health_contribution + pension_contribution

        contractor_calc = ContractorCalculation(
            fees_total=gross_income,
            taxable_base=taxable_base,
            health_contribution=health_contribution,
            pension_contribution=pension_contribution,
            total_contributions=total_contributions,
            net_amount=gross_income - total_contributions - request.deductions
        )

        # Para contratistas, no hay deducciones de empleado ni aportes de empleador
        empty_deductions = SocialSecurityDeductions(
            health=0, pension=0, solidarity_fund=0, total=0
        )
        empty_contributions = EmployerContributions(
            health=0, pension=0, arl=0, family_compensation=0, icbf=0, sena=0, total=0
        )

        total_deductions = total_contributions + request.deductions
        net_salary = gross_income - total_deductions

        return PayrollCalculationResult(
            employee_id=employee.id,
            employee_name=employee.name,
            employee_identification=employee.identification,
            employee_type=EmployeeType.CONTRACTOR,
            pay_period=request.pay_period,
            period_start=request.period_start,
            period_end=request.period_end,
            base_salary=gross_income,
            additional_income=request.additional_income,
            gross_income=gross_income,
            social_security_deductions=empty_deductions,
            employer_contributions=empty_contributions,
            special_deductions=request.deductions,
            contractor_calculation=contractor_calc,
            total_deductions=total_deductions,
            net_salary=net_salary,
            employer_cost=gross_income,  # Para contratistas, solo se pagan los honorarios
            risk_level=request.risk_level,
            current_minimum_wage=self.current_minimum_wage
        )

    def _calculate_employee_deductions(self, gross_salary: float) -> SocialSecurityDeductions:
        """Calcula deducciones de seguridad social del empleado"""

        # Salud: 4%
        health = self._round_currency(gross_salary * (self.config.health_employee / 100))

        # Pensión: 4%
        pension = self._round_currency(gross_salary * (self.config.pension_employee / 100))

        # Fondo de solidaridad pensional: 1% si salario > 4 SMLV
        solidarity_fund = 0
        if gross_salary > (self.current_minimum_wage * 4):
            solidarity_fund = self._round_currency(gross_salary * (self.config.solidarity_fund / 100))

        total = health + pension + solidarity_fund

        return SocialSecurityDeductions(
            health=health,
            pension=pension,
            solidarity_fund=solidarity_fund,
            total=total
        )

    def _calculate_employer_contributions(self, gross_salary: float, risk_level: RiskLevel) -> EmployerContributions:
        """Calcula aportes del empleador"""

        # Salud: 8.5%
        health = self._round_currency(gross_salary * (self.config.health_employer / 100))

        # Pensión: 12%
        pension = self._round_currency(gross_salary * (self.config.pension_employer / 100))

        # ARL según nivel de riesgo
        arl_rate = self.config.arl_rates.get(risk_level.value, 0.522)
        arl = self._round_currency(gross_salary * (arl_rate / 100))

        # Parafiscales (solo si salario > 10 SMLV, sino aplican las tasas completas)
        # Caja de compensación: 4%
        family_compensation = self._round_currency(gross_salary * (self.config.family_compensation / 100))

        # ICBF: 3%
        icbf = self._round_currency(gross_salary * (self.config.icbf / 100))

        # SENA: 2%
        sena = self._round_currency(gross_salary * (self.config.sena / 100))

        total = health + pension + arl + family_compensation + icbf + sena

        return EmployerContributions(
            health=health,
            pension=pension,
            arl=arl,
            family_compensation=family_compensation,
            icbf=icbf,
            sena=sena,
            total=total
        )

    def _calculate_benefits(
        self,
        employee: EmployeeResponse,
        monthly_salary: float,
        pay_period: PayPeriod
    ) -> BenefitsCalculation:
        """Calcula prestaciones sociales para empleados dependientes"""

        # Las prestaciones se calculan mensualmente y luego se prorratean según el período
        if pay_period == PayPeriod.MONTHLY:
            period_factor = 1.0
        elif pay_period == PayPeriod.BIWEEKLY:
            period_factor = 0.5
        else:  # weekly
            period_factor = 0.25

        # Vacaciones: 15 días hábiles por año (1.25 días por mes)
        vacation_days = 1.25 * period_factor
        vacation_amount = self._round_currency((monthly_salary / 30) * vacation_days)

        # Cesantías: 1 mes de salario por año (1/12 por mes)
        severance = self._round_currency((monthly_salary / 12) * period_factor)

        # Intereses sobre cesantías: 12% anual sobre cesantías
        severance_interest = self._round_currency((severance * 0.12 / 12) * period_factor)

        # Prima de servicios: 1 mes por año, pagadera en junio y diciembre (1/12 por mes)
        service_bonus = self._round_currency((monthly_salary / 12) * period_factor)

        total_benefits = vacation_amount + severance + severance_interest + service_bonus

        return BenefitsCalculation(
            vacation_days=vacation_days,
            vacation_amount=vacation_amount,
            severance=severance,
            severance_interest=severance_interest,
            service_bonus=service_bonus,
            total_benefits=total_benefits
        )

    def _determine_employee_type(self, employee: EmployeeResponse) -> EmployeeType:
        """Determina si es empleado dependiente o contratista"""
        # Por ahora asumimos que todos son empleados dependientes
        # En el futuro se puede agregar un campo employee_type al modelo Employee
        return EmployeeType.EMPLOYEE

    def _calculate_base_salary(self, employee: EmployeeResponse, request: PayrollCalculationRequest) -> float:
        """Calcula salario base según el período y tipo"""

        if request.base_salary:
            return request.base_salary

        if request.worked_hours and employee.salary_hourly:
            return request.worked_hours * employee.salary_hourly

        return self._get_employee_salary(employee, request.pay_period)

    def _get_employee_salary(self, employee: EmployeeResponse, pay_period: PayPeriod) -> float:
        """Obtiene el salario del empleado según el período"""

        if pay_period == PayPeriod.MONTHLY and employee.salary_monthly:
            return employee.salary_monthly
        elif pay_period == PayPeriod.BIWEEKLY and employee.salary_biweekly:
            return employee.salary_biweekly
        elif pay_period == PayPeriod.WEEKLY and employee.salary_biweekly:
            return employee.salary_biweekly / 2
        elif employee.salary_monthly:
            # Convertir salario mensual al período solicitado
            if pay_period == PayPeriod.BIWEEKLY:
                return employee.salary_monthly / 2
            elif pay_period == PayPeriod.WEEKLY:
                return employee.salary_monthly / 4
            else:
                return employee.salary_monthly
        else:
            raise ValueError(f"No se pudo determinar el salario para el empleado {employee.id}")

    def _round_currency(self, amount: float) -> float:
        """Redondea montos a pesos colombianos (sin centavos)"""
        return float(Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    def update_minimum_wage(self, new_amount: float, effective_date: date = None):
        """Actualiza el salario mínimo vigente"""
        self.current_minimum_wage = new_amount
        logger.info(f"Salario mínimo actualizado a ${new_amount:,.0f} efectivo desde {effective_date or date.today()}")

    def get_calculation_summary(self, calculation: PayrollCalculationResult) -> Dict[str, Any]:
        """Genera resumen del cálculo para reportes"""
        summary = {
            "empleado": {
                "nombre": calculation.employee_name,
                "identificacion": calculation.employee_identification,
                "tipo": calculation.employee_type.value
            },
            "periodo": {
                "tipo": calculation.pay_period.value,
                "inicio": calculation.period_start.isoformat(),
                "fin": calculation.period_end.isoformat()
            },
            "salarios": {
                "base": calculation.base_salary,
                "bruto": calculation.gross_income,
                "neto": calculation.net_salary,
                "costo_empleador": calculation.employer_cost
            },
            "deducciones": {
                "salud": calculation.social_security_deductions.health,
                "pension": calculation.social_security_deductions.pension,
                "solidaridad": calculation.social_security_deductions.solidarity_fund,
                "especiales": calculation.special_deductions,
                "total": calculation.total_deductions
            },
            "aportes_empleador": {
                "salud": calculation.employer_contributions.health,
                "pension": calculation.employer_contributions.pension,
                "arl": calculation.employer_contributions.arl,
                "parafiscales": {
                    "caja_compensacion": calculation.employer_contributions.family_compensation,
                    "icbf": calculation.employer_contributions.icbf,
                    "sena": calculation.employer_contributions.sena
                },
                "total": calculation.employer_contributions.total
            }
        }

        if calculation.benefits:
            summary["prestaciones"] = {
                "vacaciones": calculation.benefits.vacation_amount,
                "cesantias": calculation.benefits.severance,
                "intereses_cesantias": calculation.benefits.severance_interest,
                "prima_servicios": calculation.benefits.service_bonus,
                "total": calculation.benefits.total_benefits
            }

        if calculation.contractor_calculation:
            summary["contratista"] = {
                "honorarios_total": calculation.contractor_calculation.fees_total,
                "base_gravable": calculation.contractor_calculation.taxable_base,
                "aporte_salud": calculation.contractor_calculation.health_contribution,
                "aporte_pension": calculation.contractor_calculation.pension_contribution,
                "total_aportes": calculation.contractor_calculation.total_contributions,
                "valor_neto": calculation.contractor_calculation.net_amount
            }

        return summary

    async def process_payroll_payment(
        self,
        calculation: PayrollCalculationResult,
        processed_by: str,
        project_id: Optional[int] = None
    ) -> PayrollRecord:
        """
        Procesa el pago de nómina completo:
        1. Guarda registro en BD
        2. Registra transacción financiera
        3. Actualiza estado a 'processed'

        Args:
            calculation: Resultado del cálculo de nómina
            processed_by: Usuario que procesa (UUID)
            project_id: ID del proyecto (opcional)

        Returns:
            PayrollRecord: Registro de nómina guardado
        """
        try:
            # Importar aquí para evitar dependencias circulares
            from app.services.payroll_db import payroll_db_service
            from fastapi import HTTPException

            # Verificar nómina duplicada para el mismo empleado y período
            from app.database import get_admin_supabase
            existing_check = (
                get_admin_supabase()
                .table("payroll")
                .select("id")
                .eq("employee_id", calculation.employee_id)
                .eq("period_start", calculation.period_start.isoformat())
                .eq("period_end", calculation.period_end.isoformat())
                .limit(1)
                .execute()
            )
            if existing_check.data:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Ya existe una nómina procesada para el empleado {calculation.employee_id} "
                        f"en el período {calculation.period_start} - {calculation.period_end}. "
                        "No se permiten nóminas duplicadas para el mismo período."
                    )
                )

            # Guardar registro de nómina
            payroll_record = await payroll_db_service.save_payroll_record(
                calculation,
                processed_by
            )

            # Registrar transacción financiera
            await payroll_db_service.register_payroll_transaction(
                payroll_record,
                project_id
            )

            logger.info(f"Nómina procesada exitosamente para empleado {calculation.employee_id}")
            return payroll_record

        except Exception as e:
            logger.error(f"Error procesando pago de nómina: {str(e)}")
            raise

    async def get_payroll_history(
        self,
        employee_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ):
        """
        Obtiene historial de nómina desde la base de datos

        Args:
            employee_id: Filtrar por empleado específico
            year: Filtrar por año
            month: Filtrar por mes
            limit: Límite de registros
            offset: Desplazamiento para paginación

        Returns:
            Lista de registros de nómina
        """
        try:
            from app.services.payroll_db import payroll_db_service

            return await payroll_db_service.get_payroll_records(
                employee_id=employee_id,
                year=year,
                month=month,
                limit=limit,
                offset=offset
            )

        except Exception as e:
            logger.error(f"Error obteniendo historial de nómina: {str(e)}")
            raise

    async def get_payroll_summary_by_period(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Obtiene resumen financiero de nómina por período

        Args:
            period_start: Fecha inicio del período
            period_end: Fecha fin del período

        Returns:
            Dict: Resumen financiero del período
        """
        try:
            from app.services.payroll_db import payroll_db_service

            return await payroll_db_service.get_payroll_summary_by_period(
                period_start,
                period_end
            )

        except Exception as e:
            logger.error(f"Error obteniendo resumen de nómina: {str(e)}")
            raise

    async def mark_payroll_as_paid(
        self,
        payroll_id: int,
        receipt_url: Optional[str] = None
    ) -> bool:
        """
        Marca un registro de nómina como pagado

        Args:
            payroll_id: ID del registro de nómina
            receipt_url: URL del comprobante de pago

        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            from app.services.payroll_db import payroll_db_service

            return await payroll_db_service.mark_payroll_as_paid(
                payroll_id,
                receipt_url
            )

        except Exception as e:
            logger.error(f"Error marcando nómina como pagada: {str(e)}")
            raise

# Instancia global del servicio
payroll_service = PayrollCalculationService()