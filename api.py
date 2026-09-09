from typing import Optional, List
from urllib.parse import unquote
from html import escape

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from homologador_core import homologar_coordenada


app = FastAPI(
    title="Homologador DS38 RM API",
    description=(
        "API de apoyo técnico para homologación preliminar de zonas del D.S. N°38/2011 MMA "
        "en la Región Metropolitana."
    ),
    version="1.2.0",
)


@app.get("/")
def estado():
    return {
        "ok": True,
        "servicio": "Homologador DS38 RM API",
        "version": "1.2.0",
        "endpoints": [
            "/homologar",
            "/homologar/directo/{comuna}/{este}/{norte}",
            "/consulta/{comuna}/{este}/{norte}",
            "/homologar/punto/{id}/{este}/{norte}",
            "/homologar/lote",
            "/docs",
            "/health",
        ],
        "ejemplo_directo": "/homologar/directo/Quilicura/339240/6306531",
        "ejemplo_consulta": "/consulta/Quilicura/339240/6306531",
    }


@app.get("/health")
def health():
    return {"ok": True, "version": "1.2.0"}


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

        if isinstance(resultado, dict):
            resultado.setdefault("consulta_api", "directa_por_ruta")
            resultado.setdefault("tolerancia_m_solicitada", tolerancia_m)

        return resultado

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _valor(d, *claves, default="-"):
    """Obtiene el primer valor no vacío entre varias claves candidatas."""
    if not isinstance(d, dict):
        return default

    for clave in claves:
        if clave in d:
            valor = d.get(clave)
            if valor is not None and str(valor).strip() not in ("", "nan", "None"):
                return valor
    return default


def _fila_html(etiqueta: str, valor) -> str:
    return (
        "<tr>"
        f"<th>{escape(str(etiqueta))}</th>"
        f"<td>{escape(str(valor))}</td>"
        "</tr>"
    )


@app.get("/consulta/{comuna}/{este}/{norte}", response_class=HTMLResponse)
def consulta_html(
    comuna: str,
    este: float,
    norte: float,
    tolerancia_m: int = 50,
):
    """
    Vista HTML pública y legible de la homologación.
    Ejemplo:
    /consulta/Quilicura/339240/6306531
    """
    try:
        comuna_limpia = unquote(comuna).strip()

        r = homologar_coordenada(
            lat=None,
            lon=None,
            este=este,
            norte=norte,
            comuna=comuna_limpia,
            tolerancia_m=tolerancia_m,
        )

        if not isinstance(r, dict):
            r = {"resultado": r}

        ok = _valor(r, "ok", default=True)
        comuna_res = _valor(r, "comuna", "COMUNA", default=comuna_limpia)
        zona = _valor(r, "zona", "zona_prc", "zona_ipt", "ZONA")
        nombre_zona = _valor(r, "nombre_zona", "nombre", "NOMBRE")
        fuente_normativa = _valor(r, "fuente_normativa", "fuente")
        usos = _valor(
            r,
            "usos_suelo",
            "fundamento",
            "UPERM",
            "uso_permitido",
            "usos_permitidos",
        )
        categorias = _valor(
            r,
            "categorias",
            "categorias_oguc",
            "categorias_consideradas",
        )
        zona_ds38 = _valor(
            r,
            "zona_ds38",
            "homologacion",
            "homologacion_ds38",
        )
        limite_dia = _valor(
            r,
            "limite_dia",
            "limite_diurno",
            "npc_dia",
        )
        limite_noche = _valor(
            r,
            "limite_noche",
            "limite_nocturno",
            "npc_noche",
        )
        metodo = _valor(
            r,
            "metodo_busqueda",
            "metodo",
        )
        distancia = _valor(
            r,
            "distancia_m",
            "distancia",
        )
        criterio = _valor(
            r,
            "criterio",
            "fundamento_homologacion",
            "fundamento",
        )

        filas = "".join([
            _fila_html("Estado", ok),
            _fila_html("Comuna", comuna_res),
            _fila_html("Coordenada Este", este),
            _fila_html("Coordenada Norte", norte),
            _fila_html("Zona IPT", zona),
            _fila_html("Nombre zona", nombre_zona),
            _fila_html("Fuente normativa", fuente_normativa),
            _fila_html("Usos de suelo / fundamento", usos),
            _fila_html("Categorías consideradas", categorias),
            _fila_html("Homologación D.S. 38", zona_ds38),
            _fila_html("Límite diurno", limite_dia),
            _fila_html("Límite nocturno", limite_noche),
            _fila_html("Método de búsqueda", metodo),
            _fila_html("Distancia por tolerancia [m]", distancia),
            _fila_html("Criterio de homologación", criterio),
            _fila_html("Tolerancia solicitada [m]", tolerancia_m),
        ])

        html = f"""
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Homologador DS38 - Consulta</title>
<style>
    body {{
        font-family: Arial, Helvetica, sans-serif;
        background: #f4f7fb;
        color: #1f2937;
        margin: 0;
        padding: 24px;
    }}
    .wrap {{
        max-width: 980px;
        margin: 0 auto;
    }}
    .card {{
        background: #ffffff;
        border: 1px solid #dbe3ef;
        border-radius: 14px;
        box-shadow: 0 4px 18px rgba(0,0,0,.06);
        overflow: hidden;
    }}
    .head {{
        background: #0f172a;
        color: #ffffff;
        padding: 18px 22px;
    }}
    .head h1 {{
        margin: 0 0 6px 0;
        font-size: 24px;
    }}
    .head p {{
        margin: 0;
        color: #cbd5e1;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
    }}
    th, td {{
        padding: 12px 14px;
        border-bottom: 1px solid #e5e7eb;
        vertical-align: top;
        text-align: left;
    }}
    th {{
        width: 34%;
        background: #f8fafc;
        font-weight: 700;
    }}
    .note {{
        padding: 16px 20px;
        background: #fff7ed;
        border-top: 1px solid #fed7aa;
        color: #9a3412;
        font-size: 14px;
    }}
    .links {{
        padding: 14px 20px 20px 20px;
        background: #ffffff;
    }}
    a {{
        color: #1d4ed8;
        text-decoration: none;
        font-weight: 600;
    }}
</style>
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="head">
            <h1>Homologador DS38 RM</h1>
            <p>Consulta territorial y homologación preliminar</p>
        </div>

        <table>
            {filas}
        </table>

        <div class="note">
            Herramienta de apoyo técnico. El resultado debe verificarse con el Instrumento de Planificación Territorial vigente,
            la cartografía oficial, la ordenanza aplicable y la Res. Ex. SMA N°491/2016 antes de su uso formal.
        </div>

        <div class="links">
            <a href="/homologar/directo/{escape(comuna_limpia)}/{este}/{norte}?tolerancia_m={tolerancia_m}">
                Ver respuesta JSON
            </a>
            &nbsp;·&nbsp;
            <a href="/docs">Documentación API</a>
        </div>
    </div>
</div>
</body>
</html>
"""
        return HTMLResponse(content=html, status_code=200)

    except Exception as e:
        html = f"""
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Error</title></head>
<body style="font-family:Arial;padding:30px;">
<h2>Error de consulta</h2>
<p>{escape(str(e))}</p>
</body>
</html>
"""
        return HTMLResponse(content=html, status_code=400)


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
