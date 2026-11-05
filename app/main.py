import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, Request, Form, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, Base, get_db, SessionLocal
from app.core.security import get_current_user_optional, create_access_token
from app.models.user import User
from app.models.esavi import ESAVIRecord
from app.services.auth_service import AuthService
from app.schemas.auth import UserLogin
from app.extractor.engine import parse_int_safe

# Importación de routers de API
from app.api.routes_auth import router as auth_router
from app.api.routes_upload import router as upload_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_export import router as export_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Crear tablas en la base de datos si no existen
    Base.metadata.create_all(bind=engine)
    
    # 2. Migración segura de columnas nuevas si la tabla ya existía
    db = SessionLocal()
    try:
        from sqlalchemy import text
        for col, col_type in [
            ("jurisdiccion", "VARCHAR(100)"),
            ("requirio_hospitalizacion", "INTEGER"),
            ("recuperacion", "INTEGER")
        ]:
            try:
                db.execute(text(f"ALTER TABLE esavi_records ADD COLUMN {col} {col_type}"))
                db.commit()
            except Exception:
                db.rollback()

        # Migración segura en users
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
            db.commit()
        except Exception:
            db.rollback()

        AuthService.init_first_superuser(db)
    finally:
        db.close()
        
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de Vigilancia Epidemiológica de Eventos Supuestamente Atribuibles a la Vacunación o Inmunización (ESAVI v2)",
    version="2.0.0",
    lifespan=lifespan
)

# Montar archivos estáticos
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
templates_dir = os.path.join(current_dir, "templates")

if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Configurar motor de plantillas Jinja2
templates = Jinja2Templates(directory=templates_dir)


# ==========================================
# VISTAS WEB (HTML CON JINJA2 / HTMX)
# ==========================================

@app.get("/", response_class=HTMLResponse)
def root_redirect(user: Optional[User] = Depends(get_current_user_optional)):
    """Redirecciona al dashboard si está autenticado, o al login."""
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Muestra la página de inicio de sesión."""
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="login.html", context={"user": None, "error": None})


@app.post("/login", response_class=HTMLResponse)
def handle_login(
    request: Request,
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Procesa el formulario de login y establece la cookie HTTPOnly."""
    user_identifier = (username or email or "").strip()
    credentials = UserLogin(username=user_identifier, password=password)
    user = AuthService.authenticate_user(db, credentials)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"user": None, "error": "Credenciales incorrectas o usuario deshabilitado.", "username": user_identifier},
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    access_token = create_access_token(subject=user.id)
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@app.get("/logout")
def handle_logout():
    """Cierra la sesión eliminando la cookie y redirige a /login."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=settings.COOKIE_NAME)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Vista principal con indicadores y gráficas epidemiológicas."""
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user, "active_page": "dashboard"})


@app.get("/upload", response_class=HTMLResponse)
def upload_view(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Vista para ingesta drag-and-drop de archivos Excel."""
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="upload.html", context={"user": user, "active_page": "upload"})


@app.get("/records", response_class=HTMLResponse)
def records_view(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Vista del concentrado histórico y listado de registros."""
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    records = db.query(ESAVIRecord).order_by(ESAVIRecord.created_at.desc()).limit(50).all()
    return templates.TemplateResponse(
        request=request,
        name="records.html",
        context={"user": user, "records": records, "active_page": "records"}
    )


@app.get("/records/table", response_class=HTMLResponse)
def records_table_partial(
    request: Request,
    search: Optional[str] = Query(None),
    vacuna: Optional[str] = Query(None),
    sem_epi: Optional[str] = Query(None),
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Endpoint HTMX para filtrado en tiempo real sin recargar página."""
    if not user:
        return HTMLResponse("<span>No autorizado</span>", status_code=401)
    
    query = db.query(ESAVIRecord)
    sem_epi_parsed = parse_int_safe(sem_epi)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter((ESAVIRecord.curp.ilike(pattern)) | (ESAVIRecord.nombre_completo.ilike(pattern)))
    if vacuna and vacuna.strip():
        query = query.filter(ESAVIRecord.vacuna_1.ilike(f"%{vacuna.strip()}%"))
    if sem_epi_parsed is not None:
        query = query.filter(ESAVIRecord.sem_epi == sem_epi_parsed)

    records = query.order_by(ESAVIRecord.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(request=request, name="partials/records_table.html", context={"records": records})


# ==========================================
# REGISTRO DE ROUTERS API
# ==========================================
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(analytics_router)
app.include_router(export_router)
