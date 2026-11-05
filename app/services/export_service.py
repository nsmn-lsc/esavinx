import json
import os
from io import BytesIO
from typing import List, Optional
from datetime import date
import xlsxwriter
from sqlalchemy.orm import Session

from app.models.esavi import ESAVIRecord
from app.core.config import settings


class ExportService:
    def __init__(self, db: Session):
        self.db = db
        self.columns = self._load_columns_config()

    def _load_columns_config(self) -> List[str]:
        """Carga el orden de columnas desde el archivo JSON de configuración."""
        if os.path.exists(settings.COLUMNS_CONFIG_PATH):
            try:
                with open(settings.COLUMNS_CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Fallback de columnas mínimas si no existe el archivo
        return [
            "Folio:", "CURP", "Nombre", "Edad_Anios", "Sexo", "Entidad_Fed", "Municipio",
            "Sem_Epi", "vacuna", "dosis", "fecha_aplicacion_dia_mes_ano",
            "descripcion_cuadro_clinico", "estado_actual"
        ]

    def generate_excel(
        self,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
        sem_epi: Optional[int] = None,
        vacuna: Optional[str] = None,
        search: Optional[str] = None
    ) -> BytesIO:
        """
        Genera el libro de Excel acumulativo con formato estilizado vía XlsxWriter.
        """
        query = self.db.query(ESAVIRecord)

        if fecha_inicio:
            query = query.filter(ESAVIRecord.fecha_aplicacion_1 >= fecha_inicio)
        if fecha_fin:
            query = query.filter(ESAVIRecord.fecha_aplicacion_1 <= fecha_fin)
        if sem_epi:
            query = query.filter(ESAVIRecord.sem_epi == sem_epi)
        if vacuna and vacuna.strip():
            query = query.filter(ESAVIRecord.vacuna_1.ilike(f"%{vacuna.strip()}%"))
        if search and search.strip():
            pat = f"%{search.strip()}%"
            query = query.filter(
                (ESAVIRecord.curp.ilike(pat)) | 
                (ESAVIRecord.nombre_completo.ilike(pat))
            )

        records: List[ESAVIRecord] = query.order_by(ESAVIRecord.created_at.desc()).all()

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Concentrado_ESAVI")

        # Formatos de celda
        header_format = workbook.add_format({
            "bold": True,
            "font_name": "Calibri",
            "font_size": 11,
            "font_color": "#FFFFFF",
            "bg_color": "#1E3A8A",  # Azul marino institucional
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#D1D5DB",
        })

        data_format = workbook.add_format({
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E5E7EB",
        })

        date_format = workbook.add_format({
            "font_name": "Calibri",
            "font_size": 10,
            "num_format": "yyyy-mm-dd",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E5E7EB",
        })

        # Escribir encabezados
        for col_idx, col_name in enumerate(self.columns):
            worksheet.write(0, col_idx, col_name, header_format)

        # Rastrear anchos de columna para autofit
        col_widths = [len(col_name) + 4 for col_name in self.columns]

        # Escribir filas de datos
        for row_idx, record in enumerate(records, start=1):
            datos_json = record.datos_completos or {}
            
            for col_idx, col_name in enumerate(self.columns):
                # Extraer valor priorizando el JSONB y usando columnas modelo como fallback
                valor = datos_json.get(col_name)
                
                # Mapeos especiales si el JSONB no lo tiene con ese nombre exacto
                if valor is None:
                    if col_name == "CURP":
                        valor = record.curp
                    elif col_name == "Nombre":
                        valor = record.nombre_completo
                    elif col_name == "Edad_Anios":
                        valor = record.edad_anios
                    elif col_name == "Edad_Meses":
                        valor = record.edad_meses
                    elif col_name == "Edad_Dias":
                        valor = record.edad_dias
                    elif col_name == "Sexo":
                        valor = record.sexo
                    elif col_name == "Entidad_Fed":
                        valor = record.entidad_fed
                    elif col_name == "Municipio":
                        valor = record.municipio
                    elif col_name == "Sem_Epi":
                        valor = record.sem_epi
                    elif col_name == "vacuna":
                        valor = record.vacuna_1
                    elif col_name == "dosis":
                        valor = record.dosis_1
                    elif col_name == "fecha_aplicacion_dia_mes_ano":
                        valor = record.fecha_aplicacion_1
                    elif col_name == "estado_actual":
                        valor = record.estado_actual

                # Formateo y escritura
                if valor is None:
                    worksheet.write_blank(row_idx, col_idx, None, data_format)
                elif isinstance(valor, (date,)):
                    worksheet.write_datetime(row_idx, col_idx, valor, date_format)
                    val_len = 10
                    col_widths[col_idx] = max(col_widths[col_idx], val_len + 2)
                else:
                    val_str = str(valor)
                    worksheet.write(row_idx, col_idx, val_str, data_format)
                    col_widths[col_idx] = max(col_widths[col_idx], min(len(val_str) + 2, 50))

        # Ajustar anchos de columnas
        for col_idx, width in enumerate(col_widths):
            worksheet.set_column(col_idx, col_idx, width)

        # Congelar primera fila (headers)
        worksheet.freeze_panes(1, 0)

        workbook.close()
        output.seek(0)
        return output
