"""routes/graph_viz.py — Knowledge-graph network data for Cytoscape.js (Phase D.2.4).

Serves the API endpoints for the Link Analysis page (admin_ui/templates/link_analysis.html).
The HTML page is routed at /link-analysis in moe-infra; these JSON endpoints power it.

Queries moe-sovereign's read-only Cypher endpoint and converts the result to
the Cytoscape.js element format: {nodes: [...], edges: [...]}.

Filters let the caller narrow the graph to a specific entity type or domain.
The node limit is capped at 300 to keep initial renders responsive.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.sovereign_client import cypher_read

logger = logging.getLogger(__name__)
router = APIRouter()

_NODE_LIMIT = 300

# Cypher: returns entity nodes and their direct relationships within the result set.
# Filtering by type / domain is injected conditionally to keep the query readable.
_NETWORK_CYPHER = """
MATCH (a:Entity)
{type_filter}
{domain_filter}
WITH a LIMIT $node_limit
OPTIONAL MATCH (a)-[r]->(b:Entity)
WHERE b IS NOT NULL
RETURN a, r, b
"""


def _build_query(entity_type: Optional[str], domain: Optional[str]) -> str:
    type_filter   = f"WHERE a.type = $entity_type" if entity_type else ""
    domain_filter = (
        f"{'AND' if entity_type else 'WHERE'} a.domain = $domain"
        if domain else ""
    )
    return _NETWORK_CYPHER.format(
        type_filter=type_filter,
        domain_filter=domain_filter,
    ).strip()


def _node_id(props: dict) -> str:
    return props.get("id") or props.get("name") or str(id(props))


def _to_cytoscape(rows: list) -> dict:
    """Convert sovereign Cypher rows to Cytoscape.js {nodes, edges} format."""
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    nodes: list[dict] = []
    edges: list[dict] = []

    for row in rows:
        a = row.get("a") or {}
        b = row.get("b")
        r = row.get("r")

        for entity in (a, b):
            if entity is None:
                continue
            nid = _node_id(entity)
            if nid and nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({
                    "data": {
                        "id":     nid,
                        "label":  entity.get("name") or entity.get("title") or nid,
                        "type":   entity.get("type", ""),
                        "domain": entity.get("domain", ""),
                        "source": entity.get("source", ""),
                    }
                })

        if r and b:
            src = _node_id(a)
            tgt = _node_id(b)
            eid = f"{src}__{r.get('_type', 'REL')}__{tgt}"
            if eid not in seen_edges:
                seen_edges.add(eid)
                edges.append({
                    "data": {
                        "id":     eid,
                        "source": src,
                        "target": tgt,
                        "label":  r.get("_type", ""),
                    }
                })

    return {"nodes": nodes, "edges": edges}


@router.get("/graph/network")
async def graph_network(
    entity_type: Optional[str] = None,
    domain:      Optional[str] = None,
    limit:       int = 150,
):
    """Return knowledge-graph entities and relationships in Cytoscape.js format.

    Query params:
    - entity_type: filter to a specific Neo4j entity type
    - domain:      filter to a specific knowledge domain
    - limit:       max number of anchor nodes (1–300, default 150)
    """
    limit = max(1, min(limit, _NODE_LIMIT))
    query = _build_query(entity_type, domain)
    params: dict = {"node_limit": limit}
    if entity_type:
        params["entity_type"] = entity_type
    if domain:
        params["domain"] = domain

    try:
        result = await cypher_read(query, parameters=params, limit=limit * 3)
        rows = result.get("rows", [])
        graph = _to_cytoscape(rows)
        return {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            **graph,
        }
    except Exception as exc:
        logger.warning("graph_network error: %s", exc)
        return JSONResponse(status_code=503, content={"error": str(exc)})


@router.get("/graph/types")
async def graph_entity_types():
    """Return distinct entity types for the filter dropdown."""
    try:
        result = await cypher_read(
            "MATCH (e:Entity) WHERE e.type IS NOT NULL "
            "RETURN DISTINCT e.type AS type ORDER BY type LIMIT 50",
            limit=50,
        )
        types = [r.get("type") for r in result.get("rows", []) if r.get("type")]
        return {"types": types}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})
