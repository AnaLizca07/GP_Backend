from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta
from app.schemas.user import UserLogin, Token, UserCreate
from app.utils.auth import create_access_token, get_password_hash
from app.utils.database import supabase
from app.config import settings

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    """Registrar nuevo usuario"""
    try:
        # Crear usuario en Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not create user"
            )
        
        # Insertar en tabla users
        user_data = {
            "id": auth_response.user.id,
            "email": user.email,
            "role": user.role
        }
        
        supabase.table("users").insert(user_data).execute()
        
        # Crear token
        access_token = create_access_token(
            data={"sub": auth_response.user.id, "email": user.email, "role": user.role},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Login de usuario"""
    try:
        # Autenticar con Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Obtener datos del usuario
        user_response = supabase.table("users").select("*").eq("id", auth_response.user.id).execute()
        
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_response.data[0]
        
        # Crear token
        access_token = create_access_token(
            data={"sub": user_data["id"], "email": user_data["email"], "role": user_data["role"]},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

@router.post("/logout")
async def logout():
    """Logout de usuario"""
    # Con JWT stateless, el logout se maneja en el frontend
    # eliminando el token del localStorage
    return {"message": "Logged out successfully"}