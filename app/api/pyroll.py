from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from app.models.payroll import (
    PayrollCalculationRequest,
    PayrollCalculationResult,
    PayrollRecord,
    PayrollRecordCreate,
    PayrollRecordResponse,
    PayrollSummary,
    SocialSecurityConfig,
    MinimumWageConfig,
    PayPeriod,
    RiskLevel,
    EmployeeType
)
from app.services.payroll_db import payroll_db_service
from app.models.auth import UserResponse
from app.services.payroll import payroll_service
from app.database import get_admin_supabase
from app.services.employees import employee_service
from app.services.payroll_receipt import process_payroll_receipt
from app.services.notifications import notification_service

from app.api.deps import get_current_user, require_manager

router = APIRouter(prefix="/payroll", tags=["payroll"])

@router.post("/calculate", response_model=PayrollCalculationResult)
async def calculate_payroll(
    calculation_request: PayrollCalculationRequest,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Calcular n�mina para un empleado (RF21)

    Calcula autom�ticamente:
    - Para empleados: salud (4%), pensi�n (4%), ARL, parafiscales del empleador
    - Para contratistas: salud (12.5%) y pensi�n (16%) sobre 40% de honorarios
    - Prestaciones sociales: cesant�as, intereses, prima, vacaciones
    - Fondo de solidaridad pensional si salario > 4 SMLV

    Acceso: Solo gerentes
    """
    try:
        # Obtener datos del empleado
        employee = await employee_service.get_employee(
            calculation_request.employee_id,
            current_user
        )

        # Calcular n�mina
        result = payroll_service.calculate_employee_payroll(
            employee,
            calculation_request
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculando n�mina: {str(e)}"
        )

@router.post("/calculate/bulk")
async def calculate_bulk_payroll(
    employee_ids: List[int],
    pay_period: PayPeriod,
    period_start: date,
    period_end: date,
    risk_level: RiskLevel = RiskLevel.LEVEL_I,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Calcular n�mina para m�ltiples empleados

    �til para procesar n�mina masiva del per�odo.

    Acceso: Solo gerentes
    """
    try:
        results = []
        errors = []

        for employee_id in employee_ids:
            try:
                employee = await employee_service.get_employee(employee_id, current_user)

                request = PayrollCalculationRequest(
                    employee_id=employee_id,
                    pay_period=pay_period,
                    period_start=period_start,
                    period_end=period_end,
                    risk_level=risk_level
                )

                result = payroll_service.calculate_employee_payroll(employee, request)
                results.append(result)

            except Exception as e:
                errors.append({
                    "employee_id": employee_id,
                    "error": str(e)
                })

        return {
            "successful_calculations": len(results),
            "errors": len(errors),
            "results": results,
            "error_details": errors
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en c�lculo masivo: {str(e)}"
        )

@router.get("/calculation/{employee_id}/summary")
async def get_calculation_summary(
    employee_id: int,
    pay_period: PayPeriod,
    period_start: date,
    period_end: date,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener resumen de c�lculo de n�mina

    Acceso:
    - Gerentes: pueden ver cualquier empleado
    - Empleados: solo su propio resumen
    """
    try:
        # Verificar permisos
        if current_user.role == "employee":
            user_employee = await employee_service.get_employee_by_user_id(current_user.id, current_user)
            if user_employee.id != employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes ver tu propio resumen de n�mina"
                )

        employee = await employee_service.get_employee(employee_id, current_user)

        request = PayrollCalculationRequest(
            employee_id=employee_id,
            pay_period=pay_period,
            period_start=period_start,
            period_end=period_end
        )

        calculation = payroll_service.calculate_employee_payroll(employee, request)
        summary = payroll_service.get_calculation_summary(calculation)

        return summary

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo resumen: {str(e)}"
        )

@router.get("/config", response_model=SocialSecurityConfig)
async def get_social_security_config(
    current_user: UserResponse = Depends(require_manager)
):
    """
    Obtener configuraci�n actual de seguridad social y parafiscales

    Acceso: Solo gerentes
    """
    return payroll_service.config

@router.put("/config")
async def update_social_security_config(
    config: SocialSecurityConfig,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Actualizar configuraci�n de seguridad social

    Permite ajustar porcentajes de salud, pensi�n, ARL, parafiscales, etc.

    Acceso: Solo gerentes
    """
    try:
        payroll_service.config = config
        return {
            "message": "Configuraci�n de seguridad social actualizada exitosamente",
            "config": config
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando configuraci�n: {str(e)}"
        )

@router.put("/minimum-wage")
async def update_minimum_wage(
    amount: float,
    effective_date: Optional[date] = None,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Actualizar salario m�nimo vigente

    Importante para calcular correctamente:
    - Fondo de solidaridad pensional (> 4 SMLV)
    - Otras referencias basadas en SMLV

    Acceso: Solo gerentes
    """
    try:
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El salario m�nimo debe ser mayor a 0"
            )

        payroll_service.update_minimum_wage(amount, effective_date)

        return {
            "message": "Salario m�nimo actualizado exitosamente",
            "amount": amount,
            "effective_date": effective_date or date.today(),
            "previous_amount": payroll_service.current_minimum_wage
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando salario m�nimo: {str(e)}"
        )

@router.get("/employee/{employee_id}/breakdown")
async def get_employee_payroll_breakdown(
    employee_id: int,
    monthly_salary: Optional[float] = None,
    risk_level: RiskLevel = RiskLevel.LEVEL_I,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener desglose detallado de n�mina para un empleado

    Muestra todos los c�lculos paso a paso para transparencia.

    Acceso:
    - Gerentes: cualquier empleado
    - Empleados: solo su propio desglose
    """
    try:
        # Verificar permisos
        if current_user.role == "employee":
            user_employee = await employee_service.get_employee_by_user_id(current_user.id, current_user)
            if user_employee.id != employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes ver tu propio desglose"
                )

        employee = await employee_service.get_employee(employee_id, current_user)

        # Usar salario proporcionado o el salario mensual del empleado
        salary = monthly_salary or employee.salary_monthly
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo determinar el salario para el c�lculo"
            )

        # Calcular deducciones del empleado
        employee_deductions = payroll_service._calculate_employee_deductions(salary)

        # Calcular aportes del empleador
        employer_contributions = payroll_service._calculate_employer_contributions(salary, risk_level)

        # Calcular prestaciones
        benefits = payroll_service._calculate_benefits(employee, salary, PayPeriod.MONTHLY)

        return {
            "empleado": {
                "nombre": employee.name,
                "identificacion": employee.identification,
                "salario_base": salary
            },
            "deducciones_empleado": {
                "salud_4_porciento": employee_deductions.health,
                "pension_4_porciento": employee_deductions.pension,
                "fondo_solidaridad": employee_deductions.solidarity_fund,
                "total_deducciones": employee_deductions.total
            },
            "aportes_empleador": {
                "salud_8_5_porciento": employer_contributions.health,
                "pension_12_porciento": employer_contributions.pension,
                "arl": {
                    "nivel_riesgo": risk_level.value,
                    "porcentaje": payroll_service.config.arl_rates.get(risk_level.value, 0.522),
                    "valor": employer_contributions.arl
                },
                "parafiscales": {
                    "caja_compensacion_4_porciento": employer_contributions.family_compensation,
                    "icbf_3_porciento": employer_contributions.icbf,
                    "sena_2_porciento": employer_contributions.sena
                },
                "total_aportes": employer_contributions.total
            },
            "prestaciones_sociales": {
                "vacaciones": benefits.vacation_amount,
                "cesantias": benefits.severance,
                "intereses_cesantias": benefits.severance_interest,
                "prima_servicios": benefits.service_bonus,
                "total_prestaciones": benefits.total_benefits
            },
            "resumen": {
                "salario_bruto": salary,
                "total_descuentos_empleado": employee_deductions.total,
                "salario_neto_empleado": salary - employee_deductions.total,
                "costo_total_empleador": salary + employer_contributions.total,
                "salario_minimo_actual": payroll_service.current_minimum_wage,
                "aplica_fondo_solidaridad": salary > (payroll_service.current_minimum_wage * 4)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando desglose: {str(e)}"
        )

@router.get("/contractor/{employee_id}/breakdown")
async def get_contractor_payroll_breakdown(
    employee_id: int,
    fees_amount: float,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener desglose de seguridad social para contratistas

    Calcula sobre el 40% de los honorarios seg�n normativa colombiana.

    Acceso:
    - Gerentes: cualquier contratista
    - Empleados: solo su propio desglose
    """
    try:
        if fees_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto de honorarios debe ser mayor a 0"
            )

        # Verificar permisos
        if current_user.role == "employee":
            user_employee = await employee_service.get_employee_by_user_id(current_user.id, current_user)
            if user_employee.id != employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes ver tu propio desglose"
                )

        employee = await employee_service.get_employee(employee_id, current_user)

        # C�lculos para contratista
        base_percentage = payroll_service.config.contractor_base_percentage
        taxable_base = fees_amount * (base_percentage / 100)

        health_rate = payroll_service.config.contractor_health
        pension_rate = payroll_service.config.contractor_pension

        health_contribution = payroll_service._round_currency(taxable_base * (health_rate / 100))
        pension_contribution = payroll_service._round_currency(taxable_base * (pension_rate / 100))
        total_contributions = health_contribution + pension_contribution

        net_amount = fees_amount - total_contributions

        return {
            "contratista": {
                "nombre": employee.name,
                "identificacion": employee.identification,
                "honorarios_totales": fees_amount
            },
            "calculo": {
                "base_gravable": {
                    "porcentaje_aplicado": f"{base_percentage}%",
                    "valor": taxable_base,
                    "explicacion": f"Se toma el {base_percentage}% de los honorarios para calcular aportes"
                },
                "aportes_obligatorios": {
                    "salud": {
                        "porcentaje": f"{health_rate}%",
                        "base": taxable_base,
                        "valor": health_contribution
                    },
                    "pension": {
                        "porcentaje": f"{pension_rate}%",
                        "base": taxable_base,
                        "valor": pension_contribution
                    }
                }
            },
            "resumen": {
                "honorarios_brutos": fees_amount,
                "base_gravable_40_porciento": taxable_base,
                "total_aportes": total_contributions,
                "valor_neto_a_recibir": net_amount,
                "porcentaje_descuento_total": round((total_contributions / fees_amount) * 100, 2)
            },
            "notas": [
                "Los contratistas deben pagar sus propios aportes a seguridad social",
                "El c�lculo se hace sobre el 40% de los honorarios seg�n normativa colombiana",
                "No aplican prestaciones sociales para contratistas",
                "Es responsabilidad del contratista realizar los pagos correspondientes"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando desglose de contratista: {str(e)}"
        )

@router.post("/process", response_model=PayrollRecordResponse)
async def process_payroll_payment(
    calculation_request: PayrollCalculationRequest,
    project_id: Optional[int] = None,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Procesar pago de nómina y generar comprobante (RF21, RF22)

    Flujo:
    1. Calcula la nómina
    2. Guarda registro en base de datos
    3. Registra el pago como gasto en el módulo financiero
    4. Genera comprobante de pago
    5. TODO: Envía comprobante por correo al empleado

    Acceso: Solo gerentes
    """
    try:
        # Calcular nómina
        employee = await employee_service.get_employee(
            calculation_request.employee_id,
            current_user
        )

        calculation = payroll_service.calculate_employee_payroll(
            employee,
            calculation_request
        )

        # Procesar pago completo (BD + transacción financiera)
        payroll_record = await payroll_service.process_payroll_payment(
            calculation,
            current_user.id,
            project_id
        )

        # Obtener registro completo con datos del empleado
        payroll_response = await payroll_db_service.get_payroll_by_id(payroll_record.id)

        # RF24: Notificar al empleado que su nómina fue procesada
        try:
            emp_user_res = (
                get_admin_supabase().table("employees")
                .select("name, user_id")
                .eq("id", calculation_request.employee_id)
                .single()
                .execute()
            )
            if emp_user_res.data:
                user_res = (
                    get_admin_supabase().table("users")
                    .select("email")
                    .eq("id", emp_user_res.data["user_id"])
                    .single()
                    .execute()
                )
                if user_res.data and user_res.data.get("email"):
                    await notification_service.send_payroll_processed_notification(
                        employee_email=user_res.data["email"],
                        employee_name=emp_user_res.data["name"],
                        period_start=str(calculation_request.period_start),
                        period_end=str(calculation_request.period_end),
                        net_pay=float(calculation.net_salary),
                        receipt_url=payroll_response.receipt_url or "",
                    )
        except Exception as notify_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo enviar notificación de nómina: {notify_err}")

        return payroll_response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando pago de nómina: {str(e)}"
        )

@router.get("/voucher/{employee_id}")
async def generate_payment_voucher_endpoint(
    employee_id: int,
    pay_period: PayPeriod,
    period_start: date,
    period_end: date,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generar comprobante de pago para un empleado (RF22)

    Genera PDF con:
    - Datos del empleado y período
    - Salario base, deducciones, neto a pagar
    - Desglose completo de parafiscales
    - Número consecutivo único

    Acceso:
    - Gerentes: cualquier empleado
    - Empleados: solo su propio comprobante
    """
    try:
        # Verificar permisos
        if current_user.role == "employee":
            user_employee = await employee_service.get_employee_by_user_id(current_user.id, current_user)
            if user_employee.id != employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes ver tu propio comprobante"
                )

        employee = await employee_service.get_employee(employee_id, current_user)

        request = PayrollCalculationRequest(
            employee_id=employee_id,
            pay_period=pay_period,
            period_start=period_start,
            period_end=period_end
        )

        calculation = payroll_service.calculate_employee_payroll(employee, request)
        voucher = generate_payment_voucher(calculation)

        return voucher

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando comprobante: {str(e)}"
        )

def generate_payment_voucher(calculation: PayrollCalculationResult) -> Dict[str, Any]:
    """Genera un comprobante de pago estructurado"""

    # Generar número consecutivo (en producción sería desde BD)
    voucher_number = f"NOM-{calculation.employee_id}-{calculation.period_start.strftime('%Y%m')}-001"

    voucher = {
        "comprobante": {
            "numero": voucher_number,
            "fecha_generacion": datetime.now().isoformat(),
            "tipo": "Comprobante de Pago de Nómina",
            "periodo": f"{calculation.period_start.strftime('%d/%m/%Y')} - {calculation.period_end.strftime('%d/%m/%Y')}",
            "tipo_periodo": calculation.pay_period.value
        },
        "empleado": {
            "nombre": calculation.employee_name,
            "identificacion": calculation.employee_identification,
            "tipo": calculation.employee_type.value
        },
        "devengado": {
            "salario_base": {
                "descripcion": "Salario Base",
                "valor": calculation.base_salary
            },
            "horas_trabajadas": calculation.worked_hours if calculation.worked_hours else None,
            "tarifa_hora": calculation.hourly_rate if calculation.hourly_rate else None,
            "ingresos_adicionales": {
                "descripcion": "Otros ingresos",
                "valor": calculation.additional_income
            } if calculation.additional_income > 0 else None,
            "total_devengado": calculation.gross_income
        },
        "deducciones": {
            "seguridad_social": {
                "salud": {
                    "descripcion": "Salud (4%)",
                    "porcentaje": 4.0,
                    "valor": calculation.social_security_deductions.health
                },
                "pension": {
                    "descripcion": "Pensión (4%)",
                    "porcentaje": 4.0,
                    "valor": calculation.social_security_deductions.pension
                },
                "fondo_solidaridad": {
                    "descripcion": "Fondo Solidaridad Pensional (1%)",
                    "porcentaje": 1.0,
                    "valor": calculation.social_security_deductions.solidarity_fund
                } if calculation.social_security_deductions.solidarity_fund > 0 else None
            },
            "otras_deducciones": {
                "descripcion": "Otras deducciones",
                "valor": calculation.special_deductions
            } if calculation.special_deductions > 0 else None,
            "total_deducciones": calculation.total_deductions
        },
        "neto_a_pagar": calculation.net_salary,
        "informacion_empleador": {
            "aportes": {
                "salud": {
                    "descripcion": "Salud empleador (8.5%)",
                    "valor": calculation.employer_contributions.health
                },
                "pension": {
                    "descripcion": "Pensión empleador (12%)",
                    "valor": calculation.employer_contributions.pension
                },
                "arl": {
                    "descripcion": f"ARL Nivel {calculation.risk_level.value}",
                    "valor": calculation.employer_contributions.arl
                },
                "parafiscales": {
                    "caja_compensacion": {
                        "descripcion": "Caja Compensación (4%)",
                        "valor": calculation.employer_contributions.family_compensation
                    },
                    "icbf": {
                        "descripcion": "ICBF (3%)",
                        "valor": calculation.employer_contributions.icbf
                    },
                    "sena": {
                        "descripcion": "SENA (2%)",
                        "valor": calculation.employer_contributions.sena
                    }
                },
                "total_aportes_empleador": calculation.employer_contributions.total
            },
            "costo_total_empleador": calculation.employer_cost
        },
        "prestaciones_sociales": {
            "vacaciones": calculation.benefits.vacation_amount if calculation.benefits else 0,
            "cesantias": calculation.benefits.severance if calculation.benefits else 0,
            "intereses_cesantias": calculation.benefits.severance_interest if calculation.benefits else 0,
            "prima_servicios": calculation.benefits.service_bonus if calculation.benefits else 0,
            "total_prestaciones": calculation.benefits.total_benefits if calculation.benefits else 0
        } if calculation.employee_type == EmployeeType.EMPLOYEE else None,
        "contratista": calculation.contractor_calculation.__dict__ if calculation.contractor_calculation else None,
        "legal": {
            "cumple_normativa_colombiana": True,
            "salario_minimo_referencia": calculation.current_minimum_wage,
            "fecha_calculo": calculation.calculation_date.isoformat(),
            "observaciones": [
                "Este comprobante cumple con la normatividad laboral colombiana vigente",
                "Los aportes a seguridad social son obligatorios según la Ley 100 de 1993",
                "Las prestaciones sociales se calculan según el Código Sustantivo del Trabajo"
            ] if calculation.employee_type == EmployeeType.EMPLOYEE else [
                "Contrato por prestación de servicios según normativa colombiana",
                "El contratista es responsable de sus aportes a seguridad social",
                "No aplican prestaciones sociales para este tipo de contrato"
            ]
        }
    }

    return voucher

@router.get("/employee/{employee_id}/history")
async def get_employee_payroll_history(
    employee_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(20, ge=1, le=100, description="Elementos por página"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener historial de nómina del empleado

    Permite filtrar por año y mes específico con paginación.

    Acceso:
    - Gerentes: cualquier empleado
    - Empleados: solo su propio historial
    """
    try:
        # Verificar permisos
        if current_user.role == "employee":
            user_employee = await employee_service.get_employee_by_user_id(current_user.id, current_user)
            if user_employee.id != employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes ver tu propio historial"
                )

        # Obtener historial desde la base de datos
        offset = (page - 1) * limit
        payroll_records = await payroll_service.get_payroll_history(
            employee_id=employee_id,
            year=year,
            month=month,
            limit=limit,
            offset=offset
        )

        # Calcular resumen
        total_records = len(payroll_records)
        total_base_salary = sum(record.base_salary for record in payroll_records)
        total_net_pay = sum(record.net_pay for record in payroll_records)
        total_deductions = sum(
            sum(record.deductions.values()) for record in payroll_records
        )

        return {
            "employee_id": employee_id,
            "filters": {
                "year": year,
                "month": month
            },
            "pagination": {
                "page": page,
                "limit": limit,
                "total_records": total_records
            },
            "payroll_records": payroll_records,
            "summary": {
                "total_records": total_records,
                "total_base_salary": total_base_salary,
                "total_deductions": total_deductions,
                "total_net_pay": total_net_pay
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo historial: {str(e)}"
        )

@router.get("/records/{payroll_id}", response_model=PayrollRecordResponse)
async def get_payroll_record(
    payroll_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener un registro específico de nómina por ID

    Acceso:
    - Gerentes: cualquier registro
    - Empleados: solo sus propios registros
    """
    try:
        # Obtener registro
        payroll_record = await payroll_db_service.get_payroll_by_id(payroll_id)

        if not payroll_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de nómina no encontrado"
            )

        # Verificar permisos para empleados
        if current_user.role == "employee":
            user_employee = await employee_service.get_employee_by_user_id(current_user.id, current_user)
            if payroll_record.employee_id != user_employee.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para ver este registro"
                )

        return payroll_record

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo registro de nómina: {str(e)}"
        )

@router.put("/records/{payroll_id}/mark-as-paid")
async def mark_payroll_as_paid_endpoint(
    payroll_id: int,
    receipt_url: Optional[str] = None,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Marcar registro de nómina como pagado.

    Al marcar como pagado:
    1. Obtiene el registro completo de nómina
    2. Genera un PDF comprobante de pago
    3. Lo sube a Supabase Storage
    4. Envía el comprobante por email al empleado
    5. Guarda la URL del comprobante en el registro

    Acceso: Solo gerentes
    """
    try:
        # Obtener el registro completo para tener todos los datos del PDF
        record = await payroll_db_service.get_payroll_by_id(payroll_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de nómina no encontrado"
            )

        # Generar comprobante PDF, subirlo y enviar email
        generated_url = await process_payroll_receipt(
            payroll_id=payroll_id,
            employee_id=record.employee_id,
            employee_name=record.employee_name,
            period_start=record.period_start.strftime("%d/%m/%Y"),
            period_end=record.period_end.strftime("%d/%m/%Y"),
            base_salary=float(record.base_salary),
            deductions=record.deductions or {},
            employer_contributions=record.employer_contributions or {},
            benefits=record.benefits or {},
            net_pay=float(record.net_pay),
        )

        final_url = receipt_url or generated_url

        success = await payroll_service.mark_payroll_as_paid(payroll_id, final_url)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se pudo actualizar el registro de nómina"
            )

        return {
            "message": "Registro marcado como pagado exitosamente",
            "payroll_id": payroll_id,
            "receipt_url": final_url
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marcando nómina como pagada: {str(e)}"
        )

@router.get("/summary/period")
async def get_payroll_summary_by_period_endpoint(
    period_start: date,
    period_end: date,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Obtener resumen de nómina por período

    Muestra totales financieros, número de empleados, etc.

    Acceso: Solo gerentes
    """
    try:
        if period_end <= period_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de fin debe ser posterior a la fecha de inicio"
            )

        summary = await payroll_service.get_payroll_summary_by_period(
            period_start,
            period_end
        )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo resumen de período: {str(e)}"
        )

@router.get("/records")
async def get_all_payroll_records(
    status_filter: Optional[str] = Query(None, regex="^(pending|processed|paid)$", description="Filtrar por estado"),
    year: Optional[int] = None,
    month: Optional[int] = None,
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(50, ge=1, le=100, description="Elementos por página"),
    current_user: UserResponse = Depends(require_manager)
):
    """
    Obtener todos los registros de nómina (solo gerentes)

    Permite filtrar por estado, año, mes con paginación.

    Acceso: Solo gerentes
    """
    try:
        offset = (page - 1) * limit

        payroll_records = await payroll_db_service.get_payroll_records(
            status=status_filter,
            year=year,
            month=month,
            limit=limit,
            offset=offset
        )

        # Calcular resumen
        total_records = len(payroll_records)
        total_base_salary = sum(record.base_salary for record in payroll_records)
        total_net_pay = sum(record.net_pay for record in payroll_records)

        return {
            "filters": {
                "status": status_filter,
                "year": year,
                "month": month
            },
            "pagination": {
                "page": page,
                "limit": limit,
                "total_records": total_records
            },
            "payroll_records": payroll_records,
            "summary": {
                "total_records": total_records,
                "total_base_salary": total_base_salary,
                "total_net_pay": total_net_pay
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo registros de nómina: {str(e)}"
        )

@router.delete("/records/{payroll_id}")
async def delete_payroll_record(
    payroll_id: int,
    current_user: UserResponse = Depends(require_manager)
):
    """
    Eliminar registro de nómina (solo si no está pagado)

    Acceso: Solo gerentes
    """
    try:
        success = await payroll_db_service.delete_payroll_record(payroll_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de nómina no encontrado"
            )

        return {
            "message": "Registro de nómina eliminado exitosamente",
            "payroll_id": payroll_id
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando registro de nómina: {str(e)}"
        )

@router.get("/employee/{employee_id}/receipts")
async def get_employee_payment_receipts(
    employee_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Obtener comprobantes de pago de un empleado

    Retorna todos los registros de nómina en estado 'paid' con su comprobante PDF.

    Acceso:
    - Gerentes: cualquier empleado
    - Patrocinadores: solo empleados de sus proyectos
    """
    if current_user.role not in ("manager", "sponsor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sin acceso a esta información"
        )

    # Patrocinadores: verificar que el empleado esté en uno de sus proyectos
    if current_user.role == "sponsor":
        sb = get_admin_supabase()
        emp_proj = (
            sb.table("project_employees")
            .select("project_id, projects(sponsor_id)")
            .eq("employee_id", employee_id)
            .execute()
        )
        sponsor_projects = [
            r for r in (emp_proj.data or [])
            if (r.get("projects") or {}).get("sponsor_id") == current_user.id
        ]
        if not sponsor_projects:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes ver empleados de tus proyectos"
            )

    try:
        sb = get_admin_supabase()
        result = (
            sb.table("payroll")
            .select("id, period_start, period_end, net_pay, receipt_url, paid_at, status")
            .eq("employee_id", employee_id)
            .eq("status", "paid")
            .order("paid_at", desc=True)
            .execute()
        )
        return result.data or []

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo comprobantes: {str(e)}"
        )