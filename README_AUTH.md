# Sistema de Autenticación PMIS - Supabase

## Resumen

Sistema completo de autenticación para el PMIS usando **Supabase** como backend de autenticación y **FastAPI** para la API. El sistema soporta registro, login, verificación de usuarios y gestión de roles.

## Arquitectura Implementada

```
app/
├── models/
│   └── auth.py          # Modelos Pydantic para autenticación
├── services/
│   └── auth.py          # Lógica de negocio de autenticación
├── middleware/
│   └── auth.py          # Middleware personalizado para roles
├── api/
│   └── auth.py          # Endpoints REST de autenticación
├── database.py          # Cliente Supabase singleton
├── config.py           # Configuración (ya existía)
└── main.py             # Aplicación principal FastAPI
```

## Componentes Implementados

### 1. **Modelos de Datos** (`app/models/auth.py`)

- `UserRegister`: Registro de nuevos usuarios
- `UserLogin`: Login de usuarios existentes
- `UserResponse`: Datos de usuario (sin contraseña)
- `AuthResponse`: Respuesta con token y datos de usuario
- `EmployeeCreate`: Crear perfil de empleado
- `EmployeeResponse`: Datos de empleado

### 2. **Servicio de Autenticación** (`app/services/auth.py`)

```python
class AuthService:
    async def register_user(user_data: UserRegister) -> AuthResponse
    async def login_user(login_data: UserLogin) -> AuthResponse
    async def get_current_user(token: str) -> UserResponse
    async def reset_password(email: str) -> dict
    async def create_employee_profile(employee_data: EmployeeCreate) -> EmployeeResponse
```

### 3. **Endpoints REST** (`app/api/auth.py`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Registrar nuevo usuario |
| `POST` | `/api/auth/login` | Iniciar sesión |
| `GET` | `/api/auth/me` | Obtener perfil actual |
| `POST` | `/api/auth/password-reset` | Recuperar contraseña |
| `POST` | `/api/auth/employee-profile` | Crear perfil empleado |
| `POST` | `/api/auth/logout` | Cerrar sesión |
| `GET` | `/api/auth/validate-manager` | Validar rol manager |
| `GET` | `/api/auth/validate-employee` | Validar rol employee |
| `GET` | `/api/auth/validate-sponsor` | Validar rol sponsor |

### 4. **Middleware de Autenticación** (`app/middleware/auth.py`)

```python
# Dependencias para validar roles
async def require_manager(request: Request) -> UserResponse
async def require_employee(request: Request) -> UserResponse
async def require_sponsor(request: Request) -> UserResponse
async def require_manager_or_employee(request: Request) -> UserResponse
async def require_any_authenticated(request: Request) -> UserResponse
async def get_current_user_optional(request: Request) -> Optional[UserResponse]
```

## Configuración y Uso

### 1. **Variables de Entorno**

Crea un archivo `.env` basado en `.env.example`:

```bash
# Supabase Configuration
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu-supabase-anon-key

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# JWT Configuration
SECRET_KEY=tu-clave-secreta-jwt-minimo-32-caracteres
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Frontend
FRONTEND_URL=http://localhost:3000

# Environment
ENVIRONMENT=development
```

### 2. **Iniciar la Aplicación**

```bash
# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias (ya están en requirements.txt)
pip install -r requirements.txt

# Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. **Probar los Endpoints**

```bash
Probar manualmente en http://localhost:8000/docs
```

## Ejemplos de Uso

### Registro de Usuario

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "manager@example.com",
       "password": "password123",
       "role": "manager"
     }'
```

**Respuesta:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid-del-usuario",
    "email": "manager@example.com",
    "role": "manager",
    "created_at": "2026-02-15T10:00:00Z"
  }
}
```

### Login de Usuario

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "manager@example.com",
       "password": "password123"
     }'
```

### Obtener Perfil Actual

```bash
curl -X GET "http://localhost:8000/api/auth/me" \
     -H "Authorization: Bearer tu-token-jwt"
```

### Crear Perfil de Empleado

```bash
curl -X POST "http://localhost:8000/api/auth/employee-profile" \
     -H "Authorization: Bearer tu-token-jwt" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "uuid-del-usuario-employee",
       "name": "Juan Pérez",
       "identification": "12345678",
       "position": "Desarrollador Senior",
       "salary_type": "monthly",
       "salary_monthly": 5000000
     }'
```

## Sistema de Roles

### Roles Disponibles

1. **Manager** (`manager`):
   - Puede ver y gestionar todos los recursos
   - Puede crear perfiles de empleados
   - Acceso completo al sistema

2. **Employee** (`employee`):
   - Puede ver sus propias tareas y proyectos
   - Puede actualizar su perfil
   - Acceso limitado según permisos

3. **Sponsor** (`sponsor`):
   - Puede ver proyectos que patrocina
   - Puede ver tareas de sus proyectos
   - Acceso a reportes financieros de sus proyectos

### Protección de Endpoints

```python
from app.middleware.auth import require_manager, require_employee

@app.get("/admin/users")
async def get_all_users(user: UserResponse = Depends(require_manager)):
    # Solo managers pueden acceder
    pass

@app.get("/my-tasks")
async def get_my_tasks(user: UserResponse = Depends(require_employee)):
    # Solo employees pueden acceder
    pass
```

## Seguridad Implementada

### JWT Tokens
- **Algoritmo**: HS256
- **Expiración**: 30 minutos (configurable)
- **Campos**: user_id, email, role
- **Verificación**: Middleware automático

### Validaciones
- **Email**: Formato válido con `EmailStr`
- **Contraseña**: Mínimo 6 caracteres
- **Roles**: Enum restringido a valores válidos
- **Identificación**: Única en la base de datos

### Audit Logs
- Se registra cada login en `audit_logs`
- Incluye: user_id, acción, timestamp, datos

## Integración con Base de Datos

### Tablas Utilizadas

1. **users** - Datos básicos del usuario
2. **employees** - Perfil detallado de empleados
3. **audit_logs** - Registro de auditoría

### Supabase Auth
- **Registro**: `supabase.auth.sign_up()`
- **Login**: `supabase.auth.sign_in_with_password()`
- **Reset**: `supabase.auth.reset_password_email()`

### Row Level Security (RLS)
El sistema es compatible con las políticas RLS definidas en tu modelo de base de datos.

## Testing

### Pruebas Manuales
1. Acceder a `http://localhost:8000/docs`
2. Probar endpoints con Swagger UI
3. Verificar tokens en [jwt.io](https://jwt.io)

## Errores Comunes

### 1. Error de Configuración
```
Error: Could not create user
```
**Solución**: Verificar variables de entorno de Supabase

### 2. Error de Token
```
401 Unauthorized: Token inválido
```
**Solución**: Verificar que el token no haya expirado

### 3. Error de Base de Datos
```
APIError: duplicate key value
```
**Solución**: El email o identificación ya existe
