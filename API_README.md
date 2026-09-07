# Homologador DS38 RM – API

La app Streamlit original se mantiene sin cambios.

## Archivos nuevos
- `homologador_core.py`: reutiliza la lógica territorial y de homologación.
- `api.py`: API FastAPI.
- `render.yaml`: configuración opcional para Render.

## Despliegue en Render
1. Sube esta versión al mismo repositorio GitHub.
2. En Render: New > Web Service.
3. Conecta el repositorio.
4. Build command:
   `pip install -r requirements.txt`
5. Start command:
   `uvicorn api:app --host 0.0.0.0 --port $PORT`
6. Health check: `/health`

## Consultas

### Punto por UTM WGS84 Huso 19S
`GET /homologar?este=351566&norte=6277372`

### Punto por lat/lon
`GET /homologar?lat=-33.45&lon=-70.58`

### Forzar comuna
`GET /homologar?este=351566&norte=6277372&comuna=Puente%20Alto`

### Lote
POST `/homologar/lote`

```json
{
  "receptores": [
    {"id":"R1","este":351566,"norte":6277372},
    {"id":"R2","este":351933,"norte":6277018}
  ]
}
```

## Advertencia
La salida mantiene el carácter preliminar de la herramienta y debe verificarse contra el IPT vigente,
cartografía oficial, ordenanza correspondiente y Res. Ex. SMA N°491/2016 antes de uso formal.
