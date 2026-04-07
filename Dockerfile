# ============================================================
# Etapa 1 – builder
# Instala dependencias Python en un virtualenv aislado.
# Las herramientas de compilación sólo existen en esta etapa.
# ============================================================
FROM python:3.13-slim AS builder

WORKDIR /app

# Dependencias del sistema necesarias para compilar wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear virtualenv en una ruta predecible
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar sólo dependencias de producción
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ============================================================
# Etapa 2 – runtime
# Imagen mínima con sólo lo necesario para ejecutar la app.
# ============================================================
FROM python:3.13-slim AS runtime

# Librerías del sistema requeridas en tiempo de ejecución:
#   libmagic1       → python-magic (detección de tipos de archivo)
#   libglib2.0-0    → weasyprint / pango
#   libpango-1.0-0  → weasyprint (layout de texto)
#   libpangocairo-1.0-0 → weasyprint (renderizado)
#   libcairo2       → weasyprint
#   libgdk-pixbuf2.0-0  → weasyprint (imágenes)
#   libfontconfig1  → weasyprint (fuentes)
#   libxml2 / libxslt1.1 → parsing HTML en weasyprint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libfontconfig1 \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar el virtualenv construido en la etapa anterior
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copiar el código fuente
COPY --chown=appuser:appuser . .

USER appuser

# Puerto que expone la API
EXPOSE 8000

# Variables de entorno con valores por defecto seguros
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

# Comando de arranque — sin --reload en producción
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
