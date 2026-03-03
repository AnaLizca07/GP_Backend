"""
Ejemplos de uso del sistema de cálculo de nómina y seguridad social
Desarrollado según la normativa laboral colombiana
"""

from datetime import date, datetime
from app.models.payroll import (
    PayrollCalculationRequest,
    PayPeriod,
    RiskLevel,
    SocialSecurityConfig
)
from app.models.auth import EmployeeResponse
from app.services.payroll import payroll_service

def ejemplo_empleado_salario_minimo():
    """
    Ejemplo: Empleado con salario mínimo ($1,300,000 COP)
    """
    print("=" * 60)
    print("EJEMPLO 1: EMPLEADO CON SALARIO MÍNIMO")
    print("=" * 60)

    # Datos del empleado
    empleado = EmployeeResponse(
        id=1,
        user_id="emp-001",
        name="Juan Pérez",
        identification="12345678",
        position="Auxiliar Administrativo",
        salary_monthly=1300000,  # Salario mínimo 2024
        status="active",
        created_at=datetime.now()
    )

    # Request de cálculo
    request = PayrollCalculationRequest(
        employee_id=1,
        pay_period=PayPeriod.MONTHLY,
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 29),
        risk_level=RiskLevel.LEVEL_I
    )

    # Calcular nómina
    resultado = payroll_service.calculate_employee_payroll(empleado, request)

    print(f"Empleado: {resultado.employee_name}")
    print(f"Salario Base: ${resultado.base_salary:,.0f}")
    print(f"Ingreso Bruto: ${resultado.gross_income:,.0f}")
    print()
    print("DEDUCCIONES DEL EMPLEADO:")
    print(f"  Salud (4%): ${resultado.social_security_deductions.health:,.0f}")
    print(f"  Pensión (4%): ${resultado.social_security_deductions.pension:,.0f}")
    print(f"  Fondo Solidaridad: ${resultado.social_security_deductions.solidarity_fund:,.0f}")
    print(f"  Total Deducciones: ${resultado.total_deductions:,.0f}")
    print()
    print("APORTES DEL EMPLEADOR:")
    print(f"  Salud (8.5%): ${resultado.employer_contributions.health:,.0f}")
    print(f"  Pensión (12%): ${resultado.employer_contributions.pension:,.0f}")
    print(f"  ARL (0.522%): ${resultado.employer_contributions.arl:,.0f}")
    print(f"  Caja Compensación (4%): ${resultado.employer_contributions.family_compensation:,.0f}")
    print(f"  ICBF (3%): ${resultado.employer_contributions.icbf:,.0f}")
    print(f"  SENA (2%): ${resultado.employer_contributions.sena:,.0f}")
    print(f"  Total Aportes: ${resultado.employer_contributions.total:,.0f}")
    print()
    print("PRESTACIONES SOCIALES:")
    print(f"  Vacaciones: ${resultado.benefits.vacation_amount:,.0f}")
    print(f"  Cesantías: ${resultado.benefits.severance:,.0f}")
    print(f"  Intereses Cesantías: ${resultado.benefits.severance_interest:,.0f}")
    print(f"  Prima Servicios: ${resultado.benefits.service_bonus:,.0f}")
    print()
    print("RESUMEN:")
    print(f"  Salario Neto Empleado: ${resultado.net_salary:,.0f}")
    print(f"  Costo Total Empleador: ${resultado.employer_cost:,.0f}")
    print()

def ejemplo_empleado_alto_salario():
    """
    Ejemplo: Empleado con alto salario (> 4 SMLV) - aplica fondo de solidaridad
    """
    print("=" * 60)
    print("EJEMPLO 2: EMPLEADO CON ALTO SALARIO (> 4 SMLV)")
    print("=" * 60)

    empleado = EmployeeResponse(
        id=2,
        user_id="emp-002",
        name="María González",
        identification="87654321",
        position="Gerente de Proyectos",
        salary_monthly=6000000,  # > 4 SMLV, aplica fondo solidaridad
        status="active",
        created_at=datetime.now()
    )

    request = PayrollCalculationRequest(
        employee_id=2,
        pay_period=PayPeriod.MONTHLY,
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 29),
        risk_level=RiskLevel.LEVEL_II
    )

    resultado = payroll_service.calculate_employee_payroll(empleado, request)

    print(f"Empleado: {resultado.employee_name}")
    print(f"Salario Base: ${resultado.base_salary:,.0f}")
    print(f"Aplica Fondo Solidaridad: {resultado.base_salary > (payroll_service.current_minimum_wage * 4)}")
    print()
    print("DEDUCCIONES DEL EMPLEADO:")
    print(f"  Salud (4%): ${resultado.social_security_deductions.health:,.0f}")
    print(f"  Pensión (4%): ${resultado.social_security_deductions.pension:,.0f}")
    print(f"  Fondo Solidaridad (1%): ${resultado.social_security_deductions.solidarity_fund:,.0f}")
    print(f"  Total Deducciones: ${resultado.total_deductions:,.0f}")
    print()
    print("RESUMEN:")
    print(f"  Salario Neto Empleado: ${resultado.net_salary:,.0f}")
    print(f"  Costo Total Empleador: ${resultado.employer_cost:,.0f}")
    print()

def ejemplo_empleado_quincenal():
    """
    Ejemplo: Empleado con pago quincenal
    """
    print("=" * 60)
    print("EJEMPLO 3: EMPLEADO CON PAGO QUINCENAL")
    print("=" * 60)

    empleado = EmployeeResponse(
        id=3,
        user_id="emp-003",
        name="Carlos Rodríguez",
        identification="11223344",
        position="Desarrollador Senior",
        salary_biweekly=1800000,  # Quincenal
        salary_monthly=3600000,  # Equivalente mensual
        status="active",
        created_at=datetime.now()
    )

    request = PayrollCalculationRequest(
        employee_id=3,
        pay_period=PayPeriod.BIWEEKLY,
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 15),
        risk_level=RiskLevel.LEVEL_I
    )

    resultado = payroll_service.calculate_employee_payroll(empleado, request)

    print(f"Empleado: {resultado.employee_name}")
    print(f"Período: Quincenal")
    print(f"Salario Quincenal: ${resultado.base_salary:,.0f}")
    print(f"Salario Neto: ${resultado.net_salary:,.0f}")
    print()

def ejemplo_contratista():
    """
    Ejemplo: Contratista por prestación de servicios
    """
    print("=" * 60)
    print("EJEMPLO 4: CONTRATISTA POR PRESTACIÓN DE SERVICIOS")
    print("=" * 60)

    # Simular contratista (sería diferente en implementación real)
    contratista = EmployeeResponse(
        id=4,
        user_id="cont-001",
        name="Ana Martínez",
        identification="99887766",
        position="Consultor Especializado",
        salary_monthly=5000000,  # Honorarios mensuales
        status="active",
        created_at=datetime.now()
    )

    # Para contratista, usamos el salario como honorarios
    request = PayrollCalculationRequest(
        employee_id=4,
        pay_period=PayPeriod.MONTHLY,
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 29)
    )

    # Simular cálculo manual para contratista
    honorarios = 5000000
    base_gravable = honorarios * 0.4  # 40% de los honorarios

    print(f"Contratista: {contratista.name}")
    print(f"Honorarios Totales: ${honorarios:,.0f}")
    print(f"Base Gravable (40%): ${base_gravable:,.0f}")
    print()
    print("APORTES DEL CONTRATISTA:")

    aporte_salud = base_gravable * 0.125  # 12.5%
    aporte_pension = base_gravable * 0.16  # 16%
    total_aportes = aporte_salud + aporte_pension
    valor_neto = honorarios - total_aportes

    print(f"  Salud (12.5% sobre base): ${aporte_salud:,.0f}")
    print(f"  Pensión (16% sobre base): ${aporte_pension:,.0f}")
    print(f"  Total Aportes: ${total_aportes:,.0f}")
    print()
    print("RESUMEN:")
    print(f"  Valor Neto a Recibir: ${valor_neto:,.0f}")
    print(f"  % Descuento Total: {(total_aportes/honorarios)*100:.1f}%")
    print()

def ejemplo_empleado_por_horas():
    """
    Ejemplo: Empleado que trabaja por horas
    """
    print("=" * 60)
    print("EJEMPLO 5: EMPLEADO POR HORAS")
    print("=" * 60)

    empleado = EmployeeResponse(
        id=5,
        user_id="emp-005",
        name="Luis Torres",
        identification="55667788",
        position="Técnico Part-time",
        salary_hourly=15000,  # $15,000 por hora
        status="active",
        created_at=datetime.now()
    )

    request = PayrollCalculationRequest(
        employee_id=5,
        pay_period=PayPeriod.BIWEEKLY,
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 15),
        worked_hours=60,  # 60 horas quincenales
        risk_level=RiskLevel.LEVEL_I
    )

    resultado = payroll_service.calculate_employee_payroll(empleado, request)

    print(f"Empleado: {resultado.employee_name}")
    print(f"Horas Trabajadas: {resultado.worked_hours}")
    print(f"Tarifa por Hora: ${resultado.hourly_rate:,.0f}")
    print(f"Salario Base: ${resultado.base_salary:,.0f}")
    print(f"Salario Neto: ${resultado.net_salary:,.0f}")
    print()

def ejemplo_configuracion_personalizada():
    """
    Ejemplo: Modificar configuración de seguridad social
    """
    print("=" * 60)
    print("EJEMPLO 6: CONFIGURACIÓN PERSONALIZADA")
    print("=" * 60)

    # Mostrar configuración actual
    config_actual = payroll_service.config
    print("CONFIGURACIÓN ACTUAL:")
    print(f"  Salud Empleado: {config_actual.health_employee}%")
    print(f"  Pensión Empleado: {config_actual.pension_employee}%")
    print(f"  Salud Empleador: {config_actual.health_employer}%")
    print(f"  Pensión Empleador: {config_actual.pension_employer}%")
    print()

    # Modificar configuración temporalmente
    config_nueva = SocialSecurityConfig()
    config_nueva.health_employee = 3.5  # Ejemplo de cambio

    print("NUEVA CONFIGURACIÓN (ejemplo):")
    print(f"  Salud Empleado: {config_nueva.health_employee}%")
    print("  (Otros valores permanecen igual)")
    print()

def mostrar_ejemplo_completo():
    """
    Muestra ejemplo completo con desglose paso a paso
    """
    print("=" * 80)
    print("SISTEMA DE CÁLCULO DE NÓMINA Y SEGURIDAD SOCIAL COLOMBIA")
    print("Normativa: Ley 100 de 1993, Código Sustantivo del Trabajo")
    print("=" * 80)
    print()

    # Ejecutar todos los ejemplos
    ejemplo_empleado_salario_minimo()
    ejemplo_empleado_alto_salario()
    ejemplo_empleado_quincenal()
    ejemplo_contratista()
    ejemplo_empleado_por_horas()
    ejemplo_configuracion_personalizada()

    print("=" * 80)
    print("RESUMEN DE FUNCIONALIDADES IMPLEMENTADAS:")
    print("=" * 80)
    print("✓ Cálculo automático de deducciones empleado (salud 4%, pensión 4%)")
    print("✓ Cálculo automático de aportes empleador (salud 8.5%, pensión 12%)")
    print("✓ ARL según nivel de riesgo (I-V)")
    print("✓ Parafiscales (Caja 4%, ICBF 3%, SENA 2%)")
    print("✓ Fondo solidaridad pensional para salarios > 4 SMLV")
    print("✓ Prestaciones sociales (cesantías, intereses, prima, vacaciones)")
    print("✓ Cálculo para contratistas (40% base, salud 12.5%, pensión 16%)")
    print("✓ Diferentes períodos de pago (mensual, quincenal, semanal)")
    print("✓ Empleados por horas")
    print("✓ Generación de comprobantes de pago")
    print("✓ Configuración flexible de porcentajes")
    print()
    print("ENDPOINTS DISPONIBLES:")
    print("- POST /api/payroll/calculate - Calcular nómina")
    print("- POST /api/payroll/calculate/bulk - Cálculo masivo")
    print("- GET /api/payroll/employee/{id}/breakdown - Desglose detallado")
    print("- GET /api/payroll/contractor/{id}/breakdown - Desglose contratista")
    print("- GET /api/payroll/voucher/{id} - Generar comprobante")
    print("- POST /api/payroll/process - Procesar pago")
    print("- GET/PUT /api/payroll/config - Configuración de seguridad social")
    print("- PUT /api/payroll/minimum-wage - Actualizar salario mínimo")
    print("=" * 80)

if __name__ == "__main__":
    mostrar_ejemplo_completo()