from typing import Optional, List, Dict, Any, Union
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.esavi import ESAVIRecord
from app.schemas.esavi import ESAVIRecordResponse
from app.services.export_service import ExportService
from app.extractor.engine import parse_date_safe, parse_int_safe

router = APIRouter(tags=["Exportación y Registros"])


@router.get("/api/export/excel")
def export_excel(
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin: Optional[str] = Query(None),
    sem_epi: Optional[str] = Query(None),
    vacuna: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Genera y descarga el concentrado acumulativo en formato Excel (.xlsx).
    """
    export_service = ExportService(db)
    excel_stream = export_service.generate_excel(
        fecha_inicio=parse_date_safe(fecha_inicio),
        fecha_fin=parse_date_safe(fecha_fin),
        sem_epi=parse_int_safe(sem_epi),
        vacuna=vacuna,
        search=search
    )

    filename = f"Concentrado_ESAVI_{date.today().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/api/records", response_model=List[ESAVIRecordResponse])
def get_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, description="Búsqueda por CURP o Nombre"),
    vacuna: Optional[str] = Query(None),
    sem_epi: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista los registros clínicos con soporte para búsqueda y paginación.
    """
    query = db.query(ESAVIRecord)

    sem_epi_parsed = parse_int_safe(sem_epi)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            (ESAVIRecord.curp.ilike(search_pattern)) | 
            (ESAVIRecord.nombre_completo.ilike(search_pattern))
        )
    if vacuna and vacuna.strip():
        query = query.filter(ESAVIRecord.vacuna_1.ilike(f"%{vacuna.strip()}%"))
    if sem_epi_parsed is not None:
        query = query.filter(ESAVIRecord.sem_epi == sem_epi_parsed)

    records = query.order_by(desc(ESAVIRecord.created_at)).offset(skip).limit(limit).all()
    return records


@router.get("/api/records/{record_id}", response_model=ESAVIRecordResponse)
def get_record_detail(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el detalle completo de un registro ESAVI incluyendo todo el JSONB.
    """
    record = db.query(ESAVIRecord).filter(ESAVIRecord.id == record_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    return record
