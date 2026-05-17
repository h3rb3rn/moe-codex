"""services/geospatial.py — Geospatial investigation client (Track D.4.4).

Connects moe-codex to PostGIS (PostgreSQL + PostGIS extension) via PostgREST
to provide:
  1. Layer listing — all geometry-bearing tables in the codex_geo schema.
  2. GeoJSON export — serve a table as a GeoJSON FeatureCollection for KeplerGL.
  3. Bounding-box query — filter features within a lat/lon bounding box.
  4. Point-in-polygon — find which region contains a given coordinate.
  5. KeplerGL config generation — sensible default layer config from schema.

KeplerGL is served as a self-hosted HTML page (static files bundled with codex);
the admin UI renders it in an iframe and passes a `?config=<url>` parameter that
KeplerGL fetches as the initial dataset.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GEO_PGREST_URL = os.getenv("GEO_PGREST_URL",  "http://moe-geo-rest:3000")
GEO_TIMEOUT    = float(os.getenv("GEO_TIMEOUT", "15"))
GEO_SCHEMA     = os.getenv("GEO_SCHEMA",  "codex_geo")
GEO_MAX_FEATURES = int(os.getenv("GEO_MAX_FEATURES", "5000"))


async def health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{GEO_PGREST_URL}/")
            return r.status_code == 200
    except Exception:
        return False


async def list_layers() -> list[dict[str, Any]]:
    """Return all geometry tables in the geo schema."""
    try:
        async with httpx.AsyncClient(timeout=GEO_TIMEOUT) as c:
            r = await c.get(
                f"{GEO_PGREST_URL}/",
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                return r.json().get("definitions", [])
            return []
    except Exception as exc:
        logger.debug("list_layers: %s", exc)
        return []


async def layer_geojson(
    table: str,
    geom_column: str = "geom",
    limit: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Fetch a table as a GeoJSON FeatureCollection.

    bbox: (min_lon, min_lat, max_lon, max_lat) in WGS84.
    """
    max_features = min(limit or GEO_MAX_FEATURES, GEO_MAX_FEATURES)
    params: dict[str, str] = {
        "limit": str(max_features),
        "select": f"*,ST_AsGeoJSON({geom_column}) as _geojson",
    }
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = (
            f"ST_MakeEnvelope({min_lon},{min_lat},{max_lon},{max_lat},4326)"
        )
        params[geom_column] = f"cd.{envelope}"

    features: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=GEO_TIMEOUT) as c:
            r = await c.get(
                f"{GEO_PGREST_URL}/{GEO_SCHEMA}.{table}",
                params=params,
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                return _empty_fc(table)
            rows = r.json()
            for row in rows:
                geojson_str = row.pop("_geojson", None)
                geometry = json.loads(geojson_str) if geojson_str else None
                if geometry:
                    features.append({
                        "type":       "Feature",
                        "geometry":   geometry,
                        "properties": {k: v for k, v in row.items() if k != geom_column},
                    })
    except Exception as exc:
        logger.debug("layer_geojson %s: %s", table, exc)
        return _empty_fc(table)

    return {
        "type":     "FeatureCollection",
        "name":     table,
        "features": features,
        "count":    len(features),
    }


def _empty_fc(table: str) -> dict:
    return {"type": "FeatureCollection", "name": table, "features": [], "count": 0}


async def point_in_polygon(
    lon: float,
    lat: float,
    table: str,
    geom_column: str = "geom",
    name_column: str = "name",
) -> list[dict[str, Any]]:
    """Find all polygons in a table that contain the given point."""
    try:
        async with httpx.AsyncClient(timeout=GEO_TIMEOUT) as c:
            r = await c.get(
                f"{GEO_PGREST_URL}/{GEO_SCHEMA}.{table}",
                params={
                    geom_column: f"cd.ST_Contains(,ST_SetSRID(ST_Point({lon},{lat}),4326))",
                    "select":    f"{name_column},ST_AsGeoJSON({geom_column}) as _geojson",
                },
                headers={"Accept": "application/json"},
            )
            return r.json() if r.status_code == 200 else []
    except Exception as exc:
        logger.debug("point_in_polygon: %s", exc)
        return []


def kepler_config(layer_name: str, geojson_url: str) -> dict[str, Any]:
    """Generate a minimal KeplerGL map config for a GeoJSON layer."""
    return {
        "version": "v1",
        "config": {
            "visState": {
                "layers": [{
                    "id":   layer_name,
                    "type": "geojson",
                    "config": {
                        "dataId":  layer_name,
                        "label":   layer_name,
                        "color":   [30, 150, 190],
                        "columns": {"geojson": "_geojson"},
                        "isVisible": True,
                    },
                }],
                "interactionConfig": {
                    "tooltip": {"enabled": True, "fieldsToShow": {layer_name: []}},
                },
            },
            "mapState": {"latitude": 51.5, "longitude": 10.0, "zoom": 5},
            "mapStyle": {"styleType": "dark"},
        },
        "datasets": [{
            "version": "v1",
            "data": {
                "id": layer_name,
                "label": layer_name,
                "color": [30, 150, 190],
                "allData": [],  # client fetches from geojson_url
                "fields": [],
            },
        }],
        "geojson_url": geojson_url,
    }
