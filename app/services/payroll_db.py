from datetime import datetime, date
from typing import Optional, List, Dict, Any
import logging
from uuid import UUID

from app.database import supabase
from app.models.payroll import (
    PayrollRecord,
    PayrollRecordResponse,
    PayrollCalculationResult,
    PayPeriod
)
from app.models.auth import UserResponse

logger = logging.getLogger(__name__)

class PayrollDatabaseService:
    """Servicio para operaciones de base de datos de nómina"""

    def __init__(self):
        self.db = supabase

    async def save_payroll_record(
        self,
        calculation: PayrollCalculationResult,
        processed_by: str
    ) -> PayrollRecord:
        """
        Guarda registro de nómina en la base de datos

        Args:
            calculation: Resultado del cálculo de nómina
            processed_by: Usuario que procesa la nómina (UUID)

        Returns:
            PayrollRecord: Registro guardado
        """
        try:
            # Preparar datos para inserción
            payroll_data = {
                "employee_id": calculation.employee_id,
                "period_start": calculation.period_start.isoformat(),
                "period_end": calculation.period_end.isoformat(),
                "base_salary": float(calculation.base_salary),
                "deductions": {
                    "salud": calculation.social_security_deductions.health,
                    "pension": calculation.social_security_deductions.pension,
                    "fondo_solidaridad": calculation.social_security_deductions.solidarity_fund,
                    "otros": calculation.special_deductions
                },
                "employer_contributions": {
                    "salud": calculation.employer_contributions.health,
                    "pension": calculation.employer_contributions.pension,
                    "arl": calculation.employer_contributions.arl,
                    "caja_compensacion": calculation.employer_contributions.family_compensation,
                    "icbf": calculation.employer_contributions.icbf,
                    "sena": calculation.employer_contributions.sena
                },
                "benefits": {
                    "cesantias": calculation.benefits.severance if calculation.benefits else 0,
                    "intereses_cesantias": calculation.benefits.severance_interest if calculation.benefits else 0,
                    "prima_servicios": calculation.benefits.service_bonus if calculation.benefits else 0,
                    "vacaciones": calculation.benefits.vacation_amount if calculation.benefits else 0
                },
                "bonuses": [],  # Por ahora vacío, se puede expandir
                "net_pay": float(calculation.net_salary),
                "status": "processed",
                "processed_by": processed_by
            }

            # Insertar en la base de datos
            result = self.db.table("payroll").insert(payroll_data).execute()

            if result.data:
                record_data = result.data[0]
                logger.info(f"Registro de nómina guardado con ID: {record_data['id']}")

                # Convertir a PayrollRecord
                return PayrollRecord(
                    id=record_data["id"],
                    employee_id=record_data["employee_id"],
                    period_start=date.fromisoformat(record_data["period_start"]),
                    period_end=date.fromisoformat(record_data["period_end"]),
                    base_salary=record_data["base_salary"],
                    deductions=record_data["deductions"],
                    employer_contributions=record_data["employer_contributions"],
                    benefits=record_data["benefits"],
                    bonuses=record_data.get("bonuses", []),
                    net_pay=record_data["net_pay"],
                    status=record_data["status"],
                    receipt_url=record_data.get("receipt_url"),
                    paid_at=datetime.fromisoformat(record_data["paid_at"]) if record_data.get("paid_at") else None,
                    created_at=datetime.fromisoformat(record_data["created_at"]),
                    processed_by=record_data.get("processed_by")
                )
            else:
                raise Exception("No se pudo guardar el registro de nómina")

        except Exception as e:
            logger.error(f"Error guardando registro de nómina: {str(e)}")
            raise

    async def get_payroll_records(
        self,
        employee_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[PayrollRecordResponse]:
        """
        Obtiene registros de nómina con filtros

        Args:
            employee_id: Filtrar por empleado específico
            year: Filtrar por año
            month: Filtrar por mes
            status: Filtrar por estado (pending, processed, paid)
            limit: Límite de registros
            offset: Desplazamiento para paginación

        Returns:
            List[PayrollRecordResponse]: Lista de registros de nómina
        """
        try:
            query = self.db.table("payroll").select("""
                id,
                employee_id,
                period_start,
                period_end,
                base_salary,
                deductions,
                employer_contributions,
                benefits,
                net_pay,
                status,
                receipt_url,
                created_at,
                paid_at,
                employees!inner(name)
            """)

            # Aplicar filtros
            if employee_id:
                query = query.eq("employee_id", employee_id)

            if status:
                query = query.eq("status", status)

            if year:
                start_date = f"{year}-01-01"
                end_date = f"{year}-12-31"
                query = query.gte("period_start", start_date).lte("period_end", end_date)

            if month and year:
                # Filtrar por mes específico
                start_date = f"{year}-{month:02d}-01"
                if month == 12:
                    end_date = f"{year + 1}-01-01"
                else:
                    end_date = f"{year}-{month + 1:02d}-01"
                query = query.gte("period_start", start_date).lt("period_start", end_date)

            # Aplicar paginación y orden
            query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

            result = query.execute()

            records = []
            if result.data:
                for record_data in result.data:
                    records.append(PayrollRecordResponse(
                        id=record_data["id"],
                        employee_id=record_data["employee_id"],
                        employee_name=record_data["employees"]["name"],
                        period_start=date.fromisoformat(record_data["period_start"]),
                        period_end=date.fromisoformat(record_data["period_end"]),
                        base_salary=record_data["base_salary"],
                        deductions=record_data["deductions"],
                        employer_contributions=record_data["employer_contributions"],
                        benefits=record_data["benefits"],
                        net_pay=record_data["net_pay"],
                        status=record_data["status"],
                        receipt_url=record_data.get("receipt_url"),
                        created_at=datetime.fromisoformat(record_data["created_at"]),
                        paid_at=datetime.fromisoformat(record_data["paid_at"]) if record_data.get("paid_at") else None
                    ))

            return records

        except Exception as e:
            logger.error(f"Error obteniendo registros de nómina: {str(e)}")
            raise

    async def get_payroll_by_id(self, payroll_id: int) -> Optional[PayrollRecordResponse]:
        """
        Obtiene un registro de nómina por ID

        Args:
            payroll_id: ID del registro de nómina

        Returns:
            PayrollRecordResponse: Registro de nómina o None si no existe
        """
        try:
            result = self.db.table("payroll").select("""
                id,
                employee_id,
                period_start,
                period_end,
                base_salary,
                deductions,
                employer_contributions,
                benefits,
                net_pay,
                status,
                receipt_url,
                created_at,
                paid_at,
                employees!inner(name)
            """).eq("id", payroll_id).execute()

            if result.data:
                record_data = result.data[0]
                return PayrollRecordResponse(
                    id=record_data["id"],
                    employee_id=record_data["employee_id"],
                    employee_name=record_data["employees"]["name"],
                    period_start=date.fromisoformat(record_data["period_start"]),
                    period_end=date.fromisoformat(record_data["period_end"]),
                    base_salary=record_data["base_salary"],
                    deductions=record_data["deductions"],
                    employer_contributions=record_data["employer_contributions"],
                    benefits=record_data["benefits"],
                    net_pay=record_data["net_pay"],
                    status=record_data["status"],
                    receipt_url=record_data.get("receipt_url"),
                    created_at=datetime.fromisoformat(record_data["created_at"]),
                    paid_at=datetime.fromisoformat(record_data["paid_at"]) if record_data.get("paid_at") else None
                )

            return None

        except Exception as e:
            logger.error(f"Error obteniendo registro de nómina {payroll_id}: {str(e)}")
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
            update_data = {
                "status": "paid",
                "paid_at": datetime.now().isoformat()
            }

            if receipt_url:
                update_data["receipt_url"] = receipt_url

            result = self.db.table("payroll").update(update_data).eq("id", payroll_id).execute()

            if result.data:
                logger.info(f"Registro de nómina {payroll_id} marcado como pagado")
                return True

            return False

        except Exception as e:
            logger.error(f"Error marcando nómina {payroll_id} como pagada: {str(e)}")
            raise

    async def get_payroll_summary_by_period(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Obtiene resumen de nómina por período

        Args:
            period_start: Fecha inicio del período
            period_end: Fecha fin del período

        Returns:
            Dict: Resumen financiero del período
        """
        try:
            result = self.db.table("payroll").select("""
                employee_id,
                base_salary,
                deductions,
                employer_contributions,
                benefits,
                net_pay,
                status,
                employees!inner(name)
            """).gte("period_start", period_start.isoformat())\
              .lte("period_end", period_end.isoformat()).execute()

            if not result.data:
                return {
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "total_employees": 0,
                    "total_base_salary": 0,
                    "total_deductions": 0,
                    "total_employer_contributions": 0,
                    "total_benefits": 0,
                    "total_net_pay": 0,
                    "by_status": {},
                    "employees": []
                }

            # Calcular totales
            total_employees = len(result.data)
            total_base_salary = 0
            total_deductions = 0
            total_employer_contributions = 0
            total_benefits = 0
            total_net_pay = 0
            by_status = {}
            employees = []

            for record in result.data:
                total_base_salary += record["base_salary"]
                total_net_pay += record["net_pay"]

                # Sumar deducciones
                deductions = record.get("deductions", {})
                record_deductions = sum(deductions.values())
                total_deductions += record_deductions

                # Sumar aportes empleador
                contributions = record.get("employer_contributions", {})
                record_contributions = sum(contributions.values())
                total_employer_contributions += record_contributions

                # Sumar beneficios
                benefits = record.get("benefits", {})
                record_benefits = sum(benefits.values())
                total_benefits += record_benefits

                # Contar por estado
                status = record["status"]
                if status not in by_status:
                    by_status[status] = 0
                by_status[status] += 1

                # Agregar empleado al resumen
                employees.append({
                    "employee_id": record["employee_id"],
                    "employee_name": record["employees"]["name"],
                    "base_salary": record["base_salary"],
                    "net_pay": record["net_pay"],
                    "status": status
                })

            return {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total_employees": total_employees,
                "total_base_salary": total_base_salary,
                "total_deductions": total_deductions,
                "total_employer_contributions": total_employer_contributions,
                "total_benefits": total_benefits,
                "total_net_pay": total_net_pay,
                "total_employer_cost": total_base_salary + total_employer_contributions,
                "by_status": by_status,
                "employees": employees
            }

        except Exception as e:
            logger.error(f"Error obteniendo resumen de nómina: {str(e)}")
            raise

    async def register_payroll_transaction(
        self,
        payroll_record: PayrollRecord,
        project_id: Optional[int] = None
    ) -> bool:
        """
        Registra el pago de nómina como transacción financiera

        Args:
            payroll_record: Registro de nómina
            project_id: ID del proyecto (opcional)

        Returns:
            bool: True si se registró correctamente
        """
        try:
            # Obtener nombre del empleado
            employee_result = self.db.table("employees").select("name, identification")\
                .eq("id", payroll_record.employee_id).execute()

            if not employee_result.data:
                raise Exception(f"Empleado {payroll_record.employee_id} no encontrado")

            employee_name = employee_result.data[0]["name"]
            employee_id = employee_result.data[0]["identification"]

            # Registrar transacción por el salario neto
            transaction_data = {
                "type": "expense",
                "amount": float(payroll_record.net_pay),
                "category": "salarios",
                "description": f"Pago de nómina - {employee_name} ({employee_id}) - Período {payroll_record.period_start} a {payroll_record.period_end}",
                "project_id": project_id,
                "transaction_date": payroll_record.period_end.isoformat()
            }

            result = self.db.table("transactions").insert(transaction_data).execute()

            if result.data:
                logger.info(f"Transacción financiera registrada para nómina {payroll_record.id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error registrando transacción de nómina: {str(e)}")
            raise

    async def delete_payroll_record(self, payroll_id: int) -> bool:
        """
        Elimina un registro de nómina (solo si no está pagado)

        Args:
            payroll_id: ID del registro de nómina

        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            # Verificar que no esté pagado
            check_result = self.db.table("payroll").select("status")\
                .eq("id", payroll_id).execute()

            if not check_result.data:
                return False

            if check_result.data[0]["status"] == "paid":
                raise Exception("No se puede eliminar un registro de nómina ya pagado")

            # Eliminar registro
            result = self.db.table("payroll").delete().eq("id", payroll_id).execute()

            if result.data:
                logger.info(f"Registro de nómina {payroll_id} eliminado")
                return True

            return False

        except Exception as e:
            logger.error(f"Error eliminando registro de nómina {payroll_id}: {str(e)}")
            raise

# Instancia global del servicio
payroll_db_service = PayrollDatabaseService()