from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
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


def _homologar_un_punto(
    identificador: str,
    *,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    este: Optional[float] = None,
    norte: Optional[float] = None,
    comuna: Optional[str] = None,
    tolerancia_m: int = 50,
):
    r = homologar_coordenada(
        lat=lat,
        lon=lon,
        este=este,
        norte=norte,
        comuna=comuna,
        tolerancia_m=tolerancia_m,
    )
    r["id"] = identificador
    return r


@app.get("/")
def estado():
    return {
        "ok": True,
        "servicio": "Homologador DS38 RM API",
        "version": "1.1.0",
        "endpoints": [
            "/homologar",
            "/homologar/punto/{id}/{este}/{norte}",
            "/homologar/lote-get",
            "/homologar/lote",
            "/docs",
        ],
        "ejemplo_lote_get": (
            "/homologar/lote-get?"
            "comuna=Puente%20Alto&"
            "puntos=R1:351566:6277372|R2:351933:6277018"
        ),
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


@app.get("/homologar/punto/{id}/{este}/{norte}")
def homologar_punto_get(
    id: str,
    este: float,
    norte: float,
    comuna: Optional[str] = None,
    tolerancia_m: int = 50,
):
    """
    Consulta GET simple para un receptor UTM WGS84 / Huso 19S.

    Ejemplo:
    /homologar/punto/R1/351566/6277372?comuna=Puente%20Alto
    """
    try:
        return _homologar_un_punto(
            id,
            este=este,
            norte=norte,
            comuna=comuna,
            tolerancia_m=tolerancia_m,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/homologar/lote-get")
def homologar_lote_get(
    puntos: str = Query(
        ...,
        description=(
            "Receptores en formato ID:ESTE:NORTE separados por |. "
            "Ejemplo: R1:351566:6277372|R2:351933:6277018"
        ),
    ),
    comuna: Optional[str] = Query(
        None,
        description="Comuna común para todos los puntos; puede omitirse para autodetección.",
    ),
    tolerancia_m: int = Query(
        50,
        ge=0,
        le=1000,
        description="Tolerancia espacial máxima en metros.",
    ),
):
    """
    Homologa varios receptores mediante una única URL GET.

    Formato:
    /homologar/lote-get?comuna=Puente%20Alto&puntos=R1:351566:6277372|R2:351933:6277018

    Está pensado para consultas directas desde navegadores, ChatGPT u otros
    clientes que no puedan enviar cómodamente un POST.
    """
    tokens = [x.strip() for x in puntos.split("|") if x.strip()]
    if not tokens:
        raise HTTPException(status_code=400, detail="No se informaron puntos.")

    if len(tokens) > 100:
        raise HTTPException(
            status_code=400,
            detail="Máximo 100 receptores por consulta GET.",
        )

    resultados = []
    errores_formato = []

    for token in tokens:
        partes = [x.strip() for x in token.split(":")]
        if len(partes) != 3:
            errores_formato.append(
                {
                    "entrada": token,
                    "error": "Formato esperado: ID:ESTE:NORTE",
                }
            )
            continue

        identificador, este_txt, norte_txt = partes

        if not identificador:
            errores_formato.append(
                {"entrada": token, "error": "El identificador no puede estar vacío."}
            )
            continue

        try:
            este = float(este_txt.replace(",", "."))
            norte = float(norte_txt.replace(",", "."))
        except ValueError:
            errores_formato.append(
                {
                    "entrada": token,
                    "error": "ESTE y NORTE deben ser valores numéricos.",
                }
            )
            continue

        try:
            r = _homologar_un_punto(
                identificador,
                este=este,
                norte=norte,
                comuna=comuna,
                tolerancia_m=tolerancia_m,
            )
            resultados.append(r)
        except Exception as e:
            resultados.append(
                {
                    "id": identificador,
                    "ok": False,
                    "utm_este": este,
                    "utm_norte": norte,
                    "comuna_solicitada": comuna,
                    "error": str(e),
                }
            )

    return {
        "ok": len(errores_formato) == 0
        and all(r.get("ok", False) for r in resultados),
        "cantidad_solicitada": len(tokens),
        "cantidad_procesada": len(resultados),
        "comuna_solicitada": comuna,
        "tolerancia_m": tolerancia_m,
        "resultados": resultados,
        "errores_formato": errores_formato,
    }


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
            r = _homologar_un_punto(
                p.id,
                lat=p.lat,
                lon=p.lon,
                este=p.este,
                norte=p.norte,
                comuna=p.comuna,
                tolerancia_m=p.tolerancia_m,
            )
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
        "ok": all(r.get("ok", False) for r in resultados),
        "cantidad_procesada": len(resultados),
        "resultados": resultados,
    }
