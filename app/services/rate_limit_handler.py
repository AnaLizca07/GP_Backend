from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from datetime import datetime, timedelta

class RateLimitHandler:
    def __init__(self):
        self.last_rate_limit_time: Optional[datetime] = None
        self.consecutive_rate_limits = 0

    def handle_auth_error(self, error: Exception, operation: str = "auth") -> None:
        error_msg = str(error).lower()

        if "rate limit exceeded" in error_msg or "too many requests" in error_msg:
            self._handle_rate_limit_error(operation)
        elif "user already registered" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        elif "invalid login credentials" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )
        elif "email not confirmed" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email no confirmado"
            )
        elif "signup disabled" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Registro temporalmente deshabilitado"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    def _handle_rate_limit_error(self, operation: str) -> None:
        current_time = datetime.now()

        if self.last_rate_limit_time:
            time_diff = current_time - self.last_rate_limit_time
            if time_diff < timedelta(minutes=5):
                self.consecutive_rate_limits += 1
            else:
                self.consecutive_rate_limits = 1
        else:
            self.consecutive_rate_limits = 1

        self.last_rate_limit_time = current_time
        wait_time = self._calculate_backoff_time()

        if operation == "register":
            detail = f"Demasiados intentos de registro. Espera {wait_time} minutos."
        elif operation == "login":
            detail = f"Demasiados intentos de login. Espera {wait_time} minutos."
        else:
            detail = f"Demasiadas solicitudes. Espera {wait_time} minutos."

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(wait_time * 60)}
        )

    def _calculate_backoff_time(self) -> int:
        base_wait = 2
        max_wait = 15
        wait_time = min(base_wait * (2 ** (self.consecutive_rate_limits - 1)), max_wait)
        return int(wait_time)

    def get_status_info(self) -> Dict[str, Any]:
        return {
            "last_rate_limit": self.last_rate_limit_time.isoformat() if self.last_rate_limit_time else None,
            "consecutive_limits": self.consecutive_rate_limits,
            "is_in_cooldown": (
                datetime.now() - self.last_rate_limit_time < timedelta(minutes=self._calculate_backoff_time())
            ) if self.last_rate_limit_time else False
        }

rate_limit_handler = RateLimitHandler()

def handle_supabase_auth_error(error: Exception, operation: str = "auth") -> None:
    rate_limit_handler.handle_auth_error(error, operation)

def get_rate_limit_status() -> Dict[str, Any]:
    return rate_limit_handler.get_status_info()