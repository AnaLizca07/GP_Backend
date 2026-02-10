from app.api import auth


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])