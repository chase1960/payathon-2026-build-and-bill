"""FastAPI 应用入口：装配目录、402 资源、订单与对账路由。"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import routes_catalog, routes_orders, routes_resources
from app.config import settings
from app.core.errors import PaymentError

app = FastAPI(
    title="aipay-402-gateway",
    version="0.1.0",
    description="支付宝 AI 付 Machine/Agent Pay 自动履约网关：402 账单、Payment-Proof 五校验、幂等履约",
)


@app.exception_handler(PaymentError)
async def payment_error_handler(_: Request, exc: PaymentError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": exc.message, "code": exc.code},
    )


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.provider,
            "service_id": settings.service_id}


app.include_router(routes_catalog.router)
app.include_router(routes_resources.router)
app.include_router(routes_orders.router)
