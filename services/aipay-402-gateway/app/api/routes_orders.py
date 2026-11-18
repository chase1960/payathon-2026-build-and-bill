"""订单查询、日结对账与退款路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_fulfillment_service, get_repo
from app.models.schemas import RefundRequest

router = APIRouter(tags=["orders"])


@router.get("/orders/{out_trade_no}")
def get_order(out_trade_no: str, repo=Depends(get_repo)):
    order = repo.get_order(out_trade_no)
    if order is None:
        return {"error": "order_not_found", "out_trade_no": out_trade_no}
    fulfillment = repo.get_fulfillment_by_order(out_trade_no)
    return {"order": order,
            "fulfillment_id": fulfillment["fulfillment_id"] if fulfillment else None}


@router.get("/admin/orders")
def list_orders(repo=Depends(get_repo)):
    return {"orders": repo.list_orders()}


@router.get("/admin/fulfillments")
def list_fulfillments(repo=Depends(get_repo)):
    return {"fulfillments": repo.list_fulfillments()}


@router.get("/admin/reconcile")
def reconcile(fulfillment=Depends(get_fulfillment_service)):
    return fulfillment.reconcile()


@router.post("/orders/{out_trade_no}/refund")
def refund(out_trade_no: str, body: RefundRequest,
           fulfillment=Depends(get_fulfillment_service)):
    return fulfillment.refund(out_trade_no, body.reason)
