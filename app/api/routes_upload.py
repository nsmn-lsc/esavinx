from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.esavi import BatchUploadSummary
from app.services.ingestion_service import IngestionService

router = APIRouter(tags=["Carga de Archivos"])


def _background_batch_worker(file_tuples: list, duplicate_strategy: str):
    """Worker para procesamiento de lotes en segundo plano con sesión de base de datos aislada."""
    db = SessionLocal()
    try:
        service = IngestionService(db)
        service.process_batch(file_tuples, duplicate_strategy=duplicate_strategy)
    finally:
        db.close()


@router.post("/api/upload", response_model=BatchUploadSummary)
async def upload_files(
    files: List[UploadFile] = File(...),
    duplicate_strategy: str = Form("skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingesta por lotes de 1 a N archivos clínicos .xlsx / .xlsm de ESAVI.
    Ejecuta el procesamiento CPU-bound en un hilo separado (run_in_threadpool)
    para evitar congelar el bucle de eventos principal de FastAPI.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron archivos para procesar."
        )

    file_tuples = []
    for file in files:
        filename = file.filename or "archivo_sin_nombre.xlsx"
        if not (filename.endswith(".xlsx") or filename.endswith(".xlsm") or filename.endswith(".xls")):
            continue
        content = await file.read()
        file_tuples.append((filename, content))

    if not file_tuples:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ningún archivo válido (.xlsx / .xlsm) fue proporcionado."
        )

    # Instanciar el servicio con la sesión de DB de la petición
    ingestion_service = IngestionService(db)

    # Delegar la ejecución de Pandas/OpenPyXL/DB al ThreadPool de Starlette
    # para mantener el Event Loop 100% responsivo para otras peticiones concurrentes
    summary = await run_in_threadpool(
        ingestion_service.process_batch,
        file_tuples,
        duplicate_strategy=duplicate_strategy
    )
    
    return summary


@router.post("/api/upload-async")
async def upload_files_background(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    duplicate_strategy: str = Form("skip"),
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint alternativo para lotes masivos (>50 archivos) que ejecuta la ingesta
    completamente desacoplada en segundo plano mediante BackgroundTasks.
    """
    file_tuples = []
    for file in files:
        filename = file.filename or "archivo_sin_nombre.xlsx"
        if filename.endswith((".xlsx", ".xlsm", ".xls")):
            content = await file.read()
            file_tuples.append((filename, content))

    if not file_tuples:
        raise HTTPException(status_code=400, detail="No se encontraron archivos válidos.")

    # Encolar en background tasks
    background_tasks.add_task(_background_batch_worker, file_tuples, duplicate_strategy)

    return {
        "status": "queued",
        "message": f"Se encolaron {len(file_tuples)} archivos para procesamiento en segundo plano.",
        "total_files": len(file_tuples)
    }
