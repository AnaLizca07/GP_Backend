# GP Backend - Sistema de Gestión de Proyectos

API REST desarrollada con FastAPI y Supabase para gestión de proyectos con autenticación segura.

## Prerrequisitos

Antes de comenzar, asegúrate de tener instalado:

- **Python 3.8+** - [Descargar Python](https://python.org/downloads/)
- **Git** - [Descargar Git](https://git-scm.com/downloads)
- **Cuenta de Supabase** - [Crear cuenta gratuita](https://supabase.com)

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/GP_Backend.git
cd GP_Backend
```

### 2. Crear y activar entorno virtual

**En Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**En macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo de ejemplo:
```bash
cp .env.example .env
```

Edita el archivo `.env` con tus configuraciones:

```env
# Supabase Configuration
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu-clave-anon-de-supabase

# Database
DATABASE_URL=postgresql://postgres:tu-password@db.supabase.co:5432/postgres

# JWT Configuration
SECRET_KEY=genera-una-clave-secreta-de-al-menos-32-caracteres
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Frontend
FRONTEND_URL=http://localhost:3000

# Environment
ENVIRONMENT=development
```

### 5. Configurar Supabase

1. Ve a [supabase.com](https://supabase.com) y crea una cuenta
2. Crea un nuevo proyecto
3. En **Settings > API**, copia:
   - `URL` → Variable `SUPABASE_URL`
   - `anon public key` → Variable `SUPABASE_KEY`
4. En **Settings > Database**, copia la connection string → Variable `DATABASE_URL`

### 6. Ejecutar la aplicación

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Verificar instalación

- **API Principal**: http://localhost:8000
- **Documentación interactiva**: http://localhost:8000/docs
- **Esquema OpenAPI**: http://localhost:8000/redoc

##  Desarrollo

### Comandos útiles

```bash
# Ejecutar tests
pytest

# Formatear código
black .

# Verificar sintaxis
flake8

# Verificar tipos
mypy app/

# Desactivar entorno virtual
deactivate
```

### Estructura del proyecto

```
GP_Backend/
├── app/
│   ├── main.py              # Aplicación principal FastAPI
│   ├── api/                 # Endpoints de la API
│   │   └── auth.py          # Autenticación y registro
│   ├── core/                # Configuraciones centrales
│   ├── models/              # Modelos de datos
│   └── services/            # Lógica de negocio
├── tests/                   # Tests automatizados
├── requirements.txt         # Dependencias Python
├── .env.example            # Variables de entorno ejemplo
└── README.md               # Este archivo
```


## Solución de problemas

### Error de conexión a base de datos
- Verifica que tu `DATABASE_URL` sea correcta
- Asegúrate de que tu proyecto Supabase esté activo

### Error de autenticación
- Confirma que `SUPABASE_KEY` sea la clave anon (pública)
- Verifica que `SECRET_KEY` tenga al menos 32 caracteres

### Puerto ocupado
```bash
# Cambiar puerto
uvicorn app.main:app --reload --port 8001
```
