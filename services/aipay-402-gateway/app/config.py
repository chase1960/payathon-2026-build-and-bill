"""运行配置：通过环境变量切换 mock / alipay 提供方。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    provider: str = os.getenv("AIPAY_PROVIDER", "mock")
    db_path: str = os.getenv("AIPAY_DB_PATH", "./aipay_gateway.db")
    base_url: str = os.getenv("AIPAY_BASE_URL", "http://localhost:8000")
    service_id: str = os.getenv("AIPAY_SERVICE_ID", "srv_demo_0001")
    currency: str = os.getenv("AIPAY_CURRENCY", "CNY")
    pay_before_minutes: int = int(os.getenv("AIPAY_PAY_BEFORE_MINUTES", "30"))
    app_id: str = os.getenv("AIPAY_APP_ID", "")
    app_private_key: str = os.getenv("AIPAY_APP_PRIVATE_KEY", "")
    gateway: str = os.getenv("AIPAY_GATEWAY", "https://openapi.alipay.com/gateway.do")
    sandbox_gateway: str = os.getenv(
        "AIPAY_SANDBOX_GATEWAY",
        "https://openapi-sandbox.dl.alipaydev.com/gateway.do",
    )
    use_sandbox: bool = os.getenv("AIPAY_USE_SANDBOX", "true").lower() == "true"

    @property
    def active_gateway(self) -> str:
        return self.sandbox_gateway if self.use_sandbox else self.gateway


settings = Settings()
Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
