"""目录发现路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.catalog import find_resource, get_catalog

router = APIRouter(tags=["catalog"])


@router.get("/.well-known/aipay-catalog")
def aipay_catalog() -> dict:
    return get_catalog().model_dump()


@router.get("/resources")
def list_resources() -> dict:
    catalog = get_catalog()
    return {"count": len(catalog.resources),
            "resources": [r.model_dump() for r in catalog.resources]}


@router.get("/resources/{resource_id}/meta")
def resource_meta(resource_id: str) -> dict:
    return find_resource(resource_id).model_dump()
