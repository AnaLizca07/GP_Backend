# Cargar variables de entorno ANTES de cualquier importación
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, employees, pyroll

app = FastAPI(
    title="PMIS - Sistema de Gestión de Proyectos",
    description="API para sistema de gestión de proyectos con autenticación Supabase",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(employees.router, prefix="/api", tags=["employees"])
app.include_router(pyroll.router, prefix="/api", tags=["payroll"])

@app.get("/")
async def root():
    """Endpoint de salud de la API"""
    return {
        "message": "PMIS API funcionando correctamente",
        "version": "1.0.0",
        "docs": "/docs"
    }