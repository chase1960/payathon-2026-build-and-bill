"""机器可读目录：AI Agent 通过 /.well-known/aipay-catalog 自助发现可购资源。"""
from __future__ import annotations

from app.config import settings
from app.core.errors import OFG_ORDER_NOT_FOUND, PaymentError
from app.models.schemas import Catalog, CatalogResource, EntitlementKind

DEFAULT_RESOURCES = [
    CatalogResource(
        resource_id="res_company_credit_report",
        name="企业工商信用简报",
        description="返回指定企业的工商、股权与风险条目结构化简报（JSON）。",
        price_cny="9.90",
        entitlement=EntitlementKind.one_off,
        endpoint="/resources/company-credit-report",
        tags=["data", "report", "one-off"],
    ),
    CatalogResource(
        resource_id="res_credit_query_pack",
        name="企业征信查询次数包·20 次",
        description="同一 out_trade_no 维度的 20 次程序化查询额度。",
        price_cny="29.00",
        entitlement=EntitlementKind.count_pack,
        quota=20,
        endpoint="/resources/credit-query",
        tags=["quota", "api-calls"],
    ),
    CatalogResource(
        resource_id="res_monitor_30d",
        name="风险监控时长包·30 天",
        description="30 天内持续监控目标企业并推送变更事件。",
        price_cny="39.00",
        entitlement=EntitlementKind.duration,
        quota=30,
        endpoint="/resources/risk-monitor",
        tags=["subscription", "monitoring"],
    ),
]


def get_catalog() -> Catalog:
    return Catalog(service_id=settings.service_id,
                   currency=settings.currency,
                   resources=DEFAULT_RESOURCES)


def find_resource(resource_id: str) -> CatalogResource:
    for r in DEFAULT_RESOURCES:
        if r.resource_id == resource_id:
            return r
    raise PaymentError(OFG_ORDER_NOT_FOUND, f"目录中不存在资源 {resource_id}", 404)
