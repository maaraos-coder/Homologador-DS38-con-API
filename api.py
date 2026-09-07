from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from homologador_core import homologar_coordenada

app = FastAPI(
    title="Homologador DS38 RM API",
    description=(
        "API de apoyo técnico para homologación preliminar de zonas del D.S. N°38/2011 MMA "
        "en la Región Metropolitana."
    ),
    version="1.0.0",
)

@app.get("/")
def estado():
    return {
        "ok": True,
        "servicio": "Homologador DS38 RM API",
        "version": "1.0.0",
        "endpoints": ["/homologar", "/homologar/lote", "/docs"],
    }

@app.get("/health")
def health():
    return {"ok": True}

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
            lat=lat, lon=lon, este=este, norte=norte,
            comuna=comuna, tolerancia_m=tolerancia_m
        )
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
                lat=p.lat, lon=p.lon, este=p.este, norte=p.norte,
                comuna=p.comuna, tolerancia_m=p.tolerancia_m
            )
            r["id"] = p.id
            resultados.append(r)
        except Exception as e:
            resultados.append({
                "id": p.id,
                "ok": False,
                "error": str(e),
            })
    return {"ok": True, "resultados": resultados}
