"""routes/geo.py — Geospatial investigation API (Track D.4.4).

GET  /v1/codex/geo/status                — PostGIS reachability probe
GET  /v1/codex/geo/layers                — list geometry tables
GET  /v1/codex/geo/layers/{table}/geojson — GeoJSON FeatureCollection
GET  /v1/codex/geo/layers/{table}/config  — KeplerGL map config
GET  /v1/codex/geo/pip                    — point-in-polygon lookup
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services import geospatial as svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/geo/status")
async def geo_status():
    reachable = await svc.health_check()
    return {"reachable": reachable}


@router.get("/geo/layers")
async def geo_layers():
    try:
        layers = await svc.list_layers()
        return {"layers": layers, "count": len(layers)}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@router.get("/geo/layers/{table}/geojson")
async def geo_layer_geojson(
    table:       str,
    geom_column: str   = Query(default="geom"),
    limit:       int   = Query(default=2000, ge=1, le=10000),
    min_lon:     Optional[float] = None,
    min_lat:     Optional[float] = None,
    max_lon:     Optional[float] = None,
    max_lat:     Optional[float] = None,
):
    """Return a GeoJSON FeatureCollection, optionally clipped to a bounding box."""
    bbox = None
    if all(v is not None for v in (min_lon, min_lat, max_lon, max_lat)):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    result = await svc.layer_geojson(
        table=table,
        geom_column=geom_column,
        limit=limit,
        bbox=bbox,
    )
    return result


@router.get("/geo/layers/{table}/config")
async def geo_layer_config(table: str, geom_column: str = "geom"):
    """Return a KeplerGL map config for a layer."""
    geojson_url = f"/v1/codex/geo/layers/{table}/geojson"
    config = svc.kepler_config(table, geojson_url)
    return config


@router.get("/geo/pip")
async def geo_pip(
    lon:         float  = Query(..., description="Longitude (WGS84)"),
    lat:         float  = Query(..., description="Latitude (WGS84)"),
    table:       str    = Query(...),
    geom_column: str    = Query(default="geom"),
    name_column: str    = Query(default="name"),
):
    """Find polygons containing the given point (point-in-polygon)."""
    try:
        results = await svc.point_in_polygon(
            lon=lon, lat=lat,
            table=table,
            geom_column=geom_column,
            name_column=name_column,
        )
        return {"point": {"lon": lon, "lat": lat}, "matches": results}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
