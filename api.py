from typing import Optional, List
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from homologador_core import homologar_coordenada


app = FastAPI(
    title="Homologador DS38 RM API",
    description=(
        "API de apoyo técnico para homologación preliminar de zonas del D.S. N°38/2011 MMA "
        "en la Región Metropolitana."
    ),
    version="1.1.0",
)


@app.get("/")
def estado():
    return {
        "ok": True,
        "servicio": "Homologador DS38 RM API",
        "version": "1.1.0",
        "endpoints": [
            "/homologar",
            "/homologar/directo/{comuna}/{este}/{norte}",
            "/homologar/punto/{id}/{este}/{norte}",
            "/homologar/lote",
            "/docs",
            "/health",
        ],
        "ejemplo_directo": "/homologar/directo/Quilicura/339240/6306531",
    }


@app.get("/health")
def health():
    return {"ok": True, "version": "1.1.0"}


@app.get("/homologar")
def homologar(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    este: Optional[float] = None,
    norte: Optional[float] = None,
    comuna: Optional[str] = None,
    tolerancia_m: int = 50,
):
    try:
        return homologar_coordenada(
            lat=lat,
            lon=lon,
            este=este,
            norte=norte,
            comuna=comuna,
            tolerancia_m=tolerancia_m,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================
# ENDPOINT DIRECTO SIN QUERY STRING
# Pensado para clientes que siguen mejor URLs con parámetros
# incorporados en la ruta.
# Ejemplo:
# /homologar/directo/Quilicura/339240/6306531
# =========================================================
@app.get("/homologar/directo/{comuna}/{este}/{norte}")
def homologar_directo(
    comuna: str,
    este: float,
    norte: float,
    tolerancia_m: int = 50,
):
    try:
        comuna_limpia = unquote(comuna).strip()

        resultado = homologar_coordenada(
            lat=None,
            lon=None,
            este=este,
            norte=norte,
            comuna=comuna_limpia,
            tolerancia_m=tolerancia_m,
        )

        # Agregamos metadatos mínimos sin alterar el resultado del core.
        if isinstance(resultado, dict):
            resultado.setdefault("consulta_api", "directa_por_ruta")
            resultado.setdefault("tolerancia_m_solicitada", tolerancia_m)

        return resultado

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================
# ENDPOINT DE PUNTO CON ID
# Mantiene una URL cómoda para receptores R1, R2, etc.
# La comuna se entrega como query opcional.
# Ejemplo:
# /homologar/punto/R1/339240/6306531?comuna=Quilicura
# =========================================================
@app.get("/homologar/punto/{id}/{este}/{norte}")
def homologar_punto(
    id: str,
    este: float,
    norte: float,
    comuna: Optional[str] = None,
    tolerancia_m: int = 50,
):
    try:
        resultado = homologar_coordenada(
            lat=None,
            lon=None,
            este=este,
            norte=norte,
            comuna=comuna,
            tolerancia_m=tolerancia_m,
        )

        if isinstance(resultado, dict):
            resultado["id"] = id
            resultado.setdefault("consulta_api", "punto_por_ruta")
            resultado.setdefault("tolerancia_m_solicitada", tolerancia_m)

        return resultado

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class Punto(BaseModel):
    id: str = Field(..., description="Identificador del receptor, por ejemplo R1")
    lat: Optional[float] = None
    lon: Optional[float] = None
    este: Optional[float] = None
    norte: Optional[float] = None
    comuna: Optional[str] = None
    tolerancia_m: int = 50


class Lote(BaseModel):
    receptores: List[Punto]


@app.post("/homologar/lote")
def homologar_lote(payload: Lote):
    resultados = []

    for p in payload.receptores:
        try:
            r = homologar_coordenada(
                lat=p.lat,
                lon=p.lon,
                este=p.este,
                norte=p.norte,
                comuna=p.comuna,
                tolerancia_m=p.tolerancia_m,
            )

            if isinstance(r, dict):
                r["id"] = p.id

            resultados.append(r)

        except Exception as e:
            resultados.append(
                {
                    "id": p.id,
                    "ok": False,
                    "error": str(e),
                }
            )

    return {
        "ok": True,
        "cantidad": len(resultados),
        "resultados": resultados,
    }
