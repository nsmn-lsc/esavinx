from typing import List, Tuple, Optional
from io import BytesIO
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.esavi import ESAVIRecord
from app.extractor.engine import ESAVIExtractor
from app.schemas.esavi import UploadFileResult, BatchUploadSummary


class IngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = ESAVIExtractor()

    def process_file_content(
        self,
        content: bytes,
        filename: str,
        duplicate_strategy: str = "skip"  # "skip" o "update"
    ) -> UploadFileResult:
        """
        Procesa el contenido binario de un archivo Excel de ESAVI.
        """
        try:
            data = self.extractor.extraer_registro_normalizado(content, archivo_fuente=filename)
            curp = data["curp"]
            fecha_aplicacion = data["fecha_aplicacion_1"]
            vacuna = data["vacuna_1"]

            # Comprobar duplicado según la clave única compuesta
            query = self.db.query(ESAVIRecord).filter(
                ESAVIRecord.curp == curp,
                ESAVIRecord.fecha_aplicacion_1 == fecha_aplicacion,
                ESAVIRecord.vacuna_1 == vacuna,
            )
            existing = query.first()

            if existing:
                if duplicate_strategy == "update":
                    # Sobrescribir datos existentes
                    for key, val in data.items():
                        setattr(existing, key, val)
                    self.db.commit()
                    self.db.refresh(existing)
                    return UploadFileResult(
                        filename=filename,
                        status="updated_duplicate",
                        message="Registro duplicado detectado y actualizado exitosamente.",
                        curp=curp,
                        vacuna=vacuna,
                        fecha_aplicacion=str(fecha_aplicacion) if fecha_aplicacion else None,
                    )
                else:
                    # Ignorar / Skip
                    return UploadFileResult(
                        filename=filename,
                        status="skipped_duplicate",
                        message="Registro ya existente en la base de datos (ignorado).",
                        curp=curp,
                        vacuna=vacuna,
                        fecha_aplicacion=str(fecha_aplicacion) if fecha_aplicacion else None,
                    )

            # Inserción de nuevo registro
            nuevo_registro = ESAVIRecord(**data)
            self.db.add(nuevo_registro)
            self.db.commit()
            self.db.refresh(nuevo_registro)

            return UploadFileResult(
                filename=filename,
                status="success",
                message="Procesado y almacenado correctamente.",
                curp=curp,
                vacuna=vacuna,
                fecha_aplicacion=str(fecha_aplicacion) if fecha_aplicacion else None,
            )

        except Exception as e:
            self.db.rollback()
            return UploadFileResult(
                filename=filename,
                status="error",
                message=f"Error en extracción: {str(e)}",
                curp=None,
                vacuna=None,
                fecha_aplicacion=None,
            )

    def process_batch(
        self,
        files: List[Tuple[str, bytes]],
        duplicate_strategy: str = "skip"
    ) -> BatchUploadSummary:
        """
        Procesa una lista de tuplas (filename, bytes_content).
        """
        results: List[UploadFileResult] = []
        success_count = 0
        skipped_count = 0
        updated_count = 0
        error_count = 0

        for filename, content in files:
            res = self.process_file_content(content, filename, duplicate_strategy=duplicate_strategy)
            results.append(res)
            if res.status == "success":
                success_count += 1
            elif res.status == "skipped_duplicate":
                skipped_count += 1
            elif res.status == "updated_duplicate":
                updated_count += 1
            elif res.status == "error":
                error_count += 1

        return BatchUploadSummary(
            total_files=len(files),
            success_count=success_count,
            skipped_count=skipped_count,
            updated_count=updated_count,
            error_count=error_count,
            results=results,
        )
