"""routes/forms.py — JSONForms schema bridge (Phase D.2.2).

Converts Kestra flow input definitions into JSON Schema + UI Schema so the
frontend JSONForms renderer can display typed, validated input forms before
triggering a flow execution.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services import kestra as kestra_svc

logger = logging.getLogger(__name__)
router = APIRouter()

# Kestra input type → JSON Schema type mapping
_TYPE_MAP: dict[str, dict] = {
    "STRING":   {"type": "string"},
    "INT":      {"type": "integer"},
    "FLOAT":    {"type": "number"},
    "BOOLEAN":  {"type": "boolean"},
    "DATETIME": {"type": "string", "format": "date-time"},
    "DATE":     {"type": "string", "format": "date"},
    "TIME":     {"type": "string", "format": "time"},
    "DURATION": {"type": "string"},
    "URI":      {"type": "string", "format": "uri"},
    "SELECT":   {"type": "string"},
    "MULTISELECT": {"type": "array", "items": {"type": "string"}},
}


def _kestra_inputs_to_jsonschema(inputs: list[dict]) -> tuple[dict, dict]:
    """Convert a Kestra flow's inputs list into (json_schema, ui_schema) for JSONForms."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    ui_elements: list[dict] = []

    for inp in inputs:
        name = inp.get("id") or inp.get("name", "")
        if not name:
            continue

        ktype = (inp.get("type") or "STRING").upper()
        schema_prop = dict(_TYPE_MAP.get(ktype, {"type": "string"}))

        if inp.get("description"):
            schema_prop["description"] = inp["description"]
        if inp.get("defaults") is not None:
            schema_prop["default"] = inp["defaults"]
        if ktype == "SELECT" and inp.get("values"):
            schema_prop["enum"] = inp["values"]
        if ktype == "MULTISELECT" and inp.get("values"):
            schema_prop["items"] = {"type": "string", "enum": inp["values"]}

        properties[name] = schema_prop

        if not inp.get("required") is False and inp.get("defaults") is None:
            required.append(name)

        ui_elements.append({
            "type": "Control",
            "scope": f"#/properties/{name}",
            "label": inp.get("displayName") or name,
        })

    json_schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        json_schema["required"] = required

    ui_schema = {
        "type": "VerticalLayout",
        "elements": ui_elements,
    }

    return json_schema, ui_schema


@router.get("/forms/schema/{namespace}/{flow_id}")
async def get_form_schema(namespace: str, flow_id: str):
    """Return JSONForms-compatible schema for a Kestra flow's inputs.

    Response: {json_schema, ui_schema, flow_id, namespace}
    """
    if not kestra_svc.KESTRA_ENABLED:
        return JSONResponse(status_code=503, content={"error": "Kestra not available"})
    try:
        flow = await kestra_svc.get_flow(namespace, flow_id)
        inputs = flow.get("inputs") or []
        json_schema, ui_schema = _kestra_inputs_to_jsonschema(inputs)
        return {
            "namespace":   namespace,
            "flow_id":     flow_id,
            "json_schema": json_schema,
            "ui_schema":   ui_schema,
            "has_inputs":  bool(inputs),
        }
    except Exception as exc:
        logger.warning("get_form_schema %s/%s: %s", namespace, flow_id, exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.get("/forms/schemas")
async def list_form_schemas(namespace: str = "", page: int = 1, size: int = 50):
    """List all flows that have at least one input (i.e. have a renderable form)."""
    if not kestra_svc.KESTRA_ENABLED:
        return JSONResponse(status_code=503, content={"error": "Kestra not available"})
    try:
        data = await kestra_svc.list_flows(namespace=namespace, page=page, size=size)
        all_flows = data.get("results") or data.get("flows") or []
        with_inputs = [
            {"namespace": f.get("namespace"), "flow_id": f.get("id"),
             "input_count": len(f.get("inputs") or [])}
            for f in all_flows if f.get("inputs")
        ]
        return {"flows_with_inputs": with_inputs, "total": len(with_inputs)}
    except Exception as exc:
        logger.warning("list_form_schemas: %s", exc)
        return JSONResponse(status_code=502, content={"error": str(exc)})
