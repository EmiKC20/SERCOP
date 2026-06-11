"""Keyword dictionaries for professional-services opportunity matching."""

BUSINESS_LINES = {
    "Audit & Assurance": [
        "auditoria",
        "auditoría",
        "auditoria externa",
        "auditoría externa",
        "estados financieros",
        "estado financiero",
        "niif",
        "nia",
        "aseguramiento",
        "aseguramiento razonable",
        "procedimientos convenidos",
        "lavado de activos",
        "uafe",
        "revisoria fiscal",
        "revisoría fiscal",
        "control interno",
        "due diligence financiero",
        "informe financiero",
        "examen especial",
        "cumplimiento financiero",
        "dictamen",
        "auditoria de gestion",
        "auditoría de gestión",
    ],
    "Tax & Legal": [
        "tributario",
        "tributaria",
        "sri",
        "ruc",
        "declaracion de impuestos",
        "declaración de impuestos",
        "cumplimiento tributario",
        "recuperacion de impuestos",
        "recuperación de impuestos",
        "precios de transferencia",
        "asesoria juridica",
        "asesoría jurídica",
        "asesoria legal",
        "asesoría legal",
        "patrocinio judicial",
        "patrocinio administrativo",
        "gobierno corporativo",
        "compliance",
        "asesoria laboral",
        "asesoría laboral",
        "contratos",
        "litigio",
        "resolucion de conflictos",
        "resolución de conflictos",
        "derecho corporativo",
        "migratorio",
        "migratoria",
    ],
    "Business Services & Outsourcing": [
        "outsourcing contable",
        "outsourcing de nomina",
        "outsourcing de nómina",
        "nomina",
        "nómina",
        "rol de pagos",
        "contabilidad",
        "servicios contables",
        "niif pymes",
        "conciliacion",
        "conciliación",
        "cuentas por pagar",
        "cuentas por cobrar",
        "tesoreria",
        "tesorería",
        "gestion financiera",
        "gestión financiera",
        "apoyo administrativo",
        "apoyo financiero",
        "procesamiento contable",
        "cierres contables",
        "administrativo financiero",
        "administrativa financiera",
    ],
    "Advisory": [
        "consultoria",
        "consultoría",
        "management consulting",
        "diagnostico organizacional",
        "diagnóstico organizacional",
        "transformacion digital",
        "transformación digital",
        "asq",
        "asg",
        "esg",
        "sostenibilidad",
        "avaluo",
        "avalúo",
        "valoracion",
        "valoración",
        "riesgo operativo",
        "risk advisory",
        "due diligence",
        "reestructuracion",
        "reestructuración",
        "plan estrategico",
        "plan estratégico",
        "mejora de procesos",
        "modelo de gestion",
        "modelo de gestión",
        "estudio de mercado",
        "factibilidad",
        "gestion de riesgos",
        "gestión de riesgos",
    ],
}

KNOWN_BUYERS = [
    "SERVICIO DE RENTAS INTERNAS",
    "SUPERINTENDENCIA DE COMPANIAS",
    "SUPERINTENDENCIA DE COMPAÑIAS",
    "SUPERINTENDENCIA DE BANCOS",
    "BANCO CENTRAL DEL ECUADOR",
    "MINISTERIO DE ECONOMIA Y FINANZAS",
    "MINISTERIO DE ECONOMÍA Y FINANZAS",
    "EMPRESA PUBLICA",
    "EMPRESA PÚBLICA",
    "INSTITUTO ECUATORIANO DE SEGURIDAD SOCIAL",
    "IESS",
    "CORPORACION FINANCIERA NACIONAL",
    "CORPORACIÓN FINANCIERA NACIONAL",
    "BANECUADOR",
    "MUNICIPIO DEL DISTRITO METROPOLITANO DE QUITO",
    "GOBIERNO AUTONOMO DESCENTRALIZADO",
    "GOBIERNO AUTÓNOMO DESCENTRALIZADO",
]

PREFERRED_PROCUREMENT_TYPES = [
    "consultoria",
    "consultoría",
    "menor cuantia",
    "menor cuantía",
    "cotizacion",
    "cotización",
    "contratacion directa",
    "contratación directa",
    "lista corta",
]


def all_search_terms() -> list[str]:
    """Return a de-duplicated list of terms suitable for API keyword searches."""
    terms = []
    seen = set()
    for keywords in BUSINESS_LINES.values():
        for keyword in keywords:
            normalized = keyword.strip().lower()
            if len(normalized) >= 3 and normalized not in seen:
                seen.add(normalized)
                terms.append(keyword)
    return terms


def balanced_search_terms(max_per_line: int = 8) -> list[str]:
    """Return a balanced keyword sample across all business lines."""
    terms = []
    seen = set()
    for keywords in BUSINESS_LINES.values():
        added = 0
        for keyword in keywords:
            normalized = keyword.strip().lower()
            if len(normalized) < 3 or normalized in seen:
                continue
            seen.add(normalized)
            terms.append(keyword)
            added += 1
            if added >= max_per_line:
                break
    return terms
