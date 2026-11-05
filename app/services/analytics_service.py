from typing import Dict, Any, List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case

from app.models.esavi import ESAVIRecord


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_metrics(
        self,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
        vacuna: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calcula los KPIs epidemiológicos y las distribuciones para Chart.js."""
        query = self.db.query(ESAVIRecord)

        if fecha_inicio:
            query = query.filter(ESAVIRecord.fecha_aplicacion_1 >= fecha_inicio)
        if fecha_fin:
            query = query.filter(ESAVIRecord.fecha_aplicacion_1 <= fecha_fin)
        if vacuna:
            query = query.filter(ESAVIRecord.vacuna_1.ilike(f"%{vacuna}%"))

        # 1. Conteo total
        total_records = query.count()

        # 2. Conteo por sexo (1: Hombre, 2: Mujer)
        conteo_sexo = (
            query.with_entities(
                ESAVIRecord.sexo,
                func.count(ESAVIRecord.id).label("total")
            )
            .group_by(ESAVIRecord.sexo)
            .all()
        )
        total_hombres = sum(c.total for c in conteo_sexo if c.sexo == 1)
        total_mujeres = sum(c.total for c in conteo_sexo if c.sexo == 2)
        total_sexo_otro = total_records - (total_hombres + total_mujeres)

        # 3. Estado actual / Eventos Graves / Recuperación / Defunciones
        total_graves = 0
        total_recuperados = 0
        total_defunciones = 0

        all_records_status = query.with_entities(
            ESAVIRecord.requirio_hospitalizacion,
            ESAVIRecord.recuperacion,
            ESAVIRecord.estado_actual,
            ESAVIRecord.datos_completos
        ).all()

        for req_hosp, recup, est, datos in all_records_status:
            d = datos if isinstance(datos, dict) else {}
            
            # 3.1 Eventos Graves / Hospitalización: 1=Si, 2=No
            hosp_val = req_hosp if req_hosp is not None else d.get("requirio_hospitalizacion")
            if hosp_val in [1, "1", 1.0, "1.0", "si", "SI", "Si", "sí", "SÍ", "Sí"]:
                total_graves += 1

            # 3.2 Recuperación / Alta: 1=Si, 2=No
            recup_val = recup if recup is not None else d.get("recuperacion")
            if recup_val in [1, "1", 1.0, "1.0", "si", "SI", "Si", "sí", "SÍ", "Sí"]:
                total_recuperados += 1

            # 3.3 Defunciones
            est_str = str(est or d.get("estado_actual", "")).lower().strip()
            causa_def = str(d.get("causa_de_la_defuncion", "")).strip()
            if any(k in est_str for k in ["defun", "fallec", "muert"]) or (causa_def and causa_def.lower() not in ["none", "nan", ""]):
                total_defunciones += 1

        # 4. Top 10 Vacunas
        top_vacunas_raw = (
            query.with_entities(
                ESAVIRecord.vacuna_1,
                func.count(ESAVIRecord.id).label("total")
            )
            .filter(ESAVIRecord.vacuna_1.isnot(None))
            .group_by(ESAVIRecord.vacuna_1)
            .order_by(desc("total"))
            .limit(10)
            .all()
        )
        top_vacunas = [{"vacuna": v[0] or "No especificada", "total": v[1]} for v in top_vacunas_raw]

        # 5. Distribución por Semana Epidemiológica
        semanas_raw = (
            query.with_entities(
                ESAVIRecord.sem_epi,
                func.count(ESAVIRecord.id).label("total")
            )
            .filter(ESAVIRecord.sem_epi.isnot(None))
            .group_by(ESAVIRecord.sem_epi)
            .order_by(ESAVIRecord.sem_epi)
            .all()
        )
        distribucion_semanal = [{"semana": f"Semana {s[0]}", "total": s[1]} for s in semanas_raw]

        # 6. Distribución por Grupos de Edad
        grupos_edad = [
            {"label": "< 5 años", "min": 0, "max": 4, "total": 0},
            {"label": "5 - 11 años", "min": 5, "max": 11, "total": 0},
            {"label": "12 - 17 años", "min": 12, "max": 17, "total": 0},
            {"label": "18 - 39 años", "min": 18, "max": 39, "total": 0},
            {"label": "40 - 59 años", "min": 40, "max": 59, "total": 0},
            {"label": "60+ años", "min": 60, "max": 150, "total": 0},
        ]
        
        all_edades = query.with_entities(ESAVIRecord.edad_anios).all()
        for (edad,) in all_edades:
            if edad is not None:
                for g in grupos_edad:
                    if g["min"] <= edad <= g["max"]:
                        g["total"] += 1
                        break

        # 7. Distribución por las 12 Jurisdicciones / Regiones Sanitarias de Hidalgo
        REGIONES_HIDALGO = [
            {"region": "01 - Pachuca", "keywords": ["pachuca", "01", "i "], "total": 0},
            {"region": "02 - Tulancingo", "keywords": ["tulancingo", "02", "ii "], "total": 0},
            {"region": "03 - Tula", "keywords": ["tula", "03", "iii "], "total": 0},
            {"region": "04 - Huichapan", "keywords": ["huichapan", "04", "iv "], "total": 0},
            {"region": "05 - Zimapán", "keywords": ["zimapan", "zimapán", "05", "v "], "total": 0},
            {"region": "06 - Ixmiquilpan", "keywords": ["ixmiquilpan", "06", "vi "], "total": 0},
            {"region": "07 - Actopan", "keywords": ["actopan", "07", "vii "], "total": 0},
            {"region": "08 - Metztitlán", "keywords": ["metztitlan", "metztitlán", "08", "viii "], "total": 0},
            {"region": "09 - Molango", "keywords": ["molango", "09", "ix "], "total": 0},
            {"region": "10 - Huejutla", "keywords": ["huejutla", "10", "x "], "total": 0},
            {"region": "11 - Apan", "keywords": ["apan", "11", "xi "], "total": 0},
            {"region": "12 - Tizayuca", "keywords": ["tizayuca", "12", "xii "], "total": 0},
        ]

        # Extraer registros para clasificar en las 12 regiones
        registros_jurisdiccion = query.with_entities(
            ESAVIRecord.jurisdiccion,
            ESAVIRecord.municipio,
            ESAVIRecord.datos_completos
        ).all()

        otras_regiones = 0
        for jur, mun, datos in registros_jurisdiccion:
            # Buscar valor de jurisdicción en campos directos o en datos_completos
            texto_busqueda = ""
            if jur:
                texto_busqueda += f" {jur}"
            if mun:
                texto_busqueda += f" {mun}"
            if datos and isinstance(datos, dict):
                texto_busqueda += f" {datos.get('Jurisdiccion_2', '')} {datos.get('Jurisdiccion_3', '')} {datos.get('jurisdiccion_sanitaria10', '')}"

            texto_norm = texto_busqueda.lower().strip()
            
            asignado = False
            for reg in REGIONES_HIDALGO:
                if any(kw in texto_norm for kw in reg["keywords"]):
                    reg["total"] += 1
                    asignado = True
                    break
            
            if not asignado and texto_norm:
                otras_regiones += 1

        distribucion_regiones = [{"region": r["region"], "total": r["total"]} for r in REGIONES_HIDALGO]
        if otras_regiones > 0:
            distribucion_regiones.append({"region": "Otras / No especificada", "total": otras_regiones})

        return {
            "kpis": {
                "total_records": total_records,
                "total_hombres": total_hombres,
                "total_mujeres": total_mujeres,
                "total_sexo_otro": total_sexo_otro,
                "total_recuperados": total_recuperados,
                "total_defunciones": total_defunciones,
                "total_graves": total_graves,
            },
            "top_vacunas": top_vacunas,
            "distribucion_semanal": distribucion_semanal,
            "distribucion_edad": grupos_edad,
            "distribucion_regiones": distribucion_regiones,
        }
