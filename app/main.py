# Cargar variables de entorno ANTES de cualquier importación
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, employees, pyroll, projects, tasks, finance, kpis, reports, okrs, ratings


async def ensure_storage_buckets():
    """Crea los buckets de Supabase Storage si no existen."""
    try:
        from app.database import get_admin_supabase
        client = get_admin_supabase()

        required_buckets = [
            ("deliverables", True),      # archivos entregables de tareas
            ("resumes", True),           # hojas de vida de empleados
            ("payroll-receipts", True),  # comprobantes de nómina
        ]

        existing = client.storage.list_buckets()
        existing_names = {b.name for b in existing}

        for name, is_public in required_buckets:
            if name not in existing_names:
                client.storage.create_bucket(name, options={"public": is_public})
                print(f"✓ Bucket '{name}' creado")
            else:
                print(f"✓ Bucket '{name}' ya existe")
    except Exception as e:
        print(f"⚠️  Error verificando/creando buckets de Storage: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_storage_buckets()
    yield


app = FastAPI(
    title="ProjeGest — Sistema de Gestión de Proyectos",
    description="API para sistema de gestión de proyectos con autenticación Supabase",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(employees.router, prefix="/api", tags=["employees"])
app.include_router(pyroll.router, prefix="/api", tags=["payroll"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(finance.router, prefix="/api", tags=["finance"])
app.include_router(kpis.router, prefix="/api", tags=["kpis"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(okrs.router, prefix="/api", tags=["okrs"])
app.include_router(ratings.router, prefix="/api", tags=["ratings"])


@app.get("/")
async def root():
    return {
        "message": "ProjeGest API funcionando correctamente",
        "version": "1.0.0",
        "docs": "/docs",
    }
