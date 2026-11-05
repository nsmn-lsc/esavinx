from typing import Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.extractor.engine import parse_date_safe

router = APIRouter(tags=["Analítica"])


@router.get("/api/analytics/metrics")
def get_analytics_metrics(
    fecha_inicio: Optional[str] = Query(None, description="Fecha de inicio de aplicación"),
    fecha_fin: Optional[str] = Query(None, description="Fecha de fin de aplicación"),
    vacuna: Optional[str] = Query(None, description="Filtrar por vacuna"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retorna KPIs y distribuciones estadísticas para visualización en Chart.js.
    """
    analytics_service = AnalyticsService(db)
    return analytics_service.get_dashboard_metrics(
        fecha_inicio=parse_date_safe(fecha_inicio),
        fecha_fin=parse_date_safe(fecha_fin),
        vacuna=vacuna.strip() if vacuna and vacuna.strip() else None
    )
