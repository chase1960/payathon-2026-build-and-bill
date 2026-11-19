import os

# 必须在导入 app.config 之前固定测试环境
os.environ.setdefault("AIPAY_PROVIDER", "mock")
os.environ.setdefault("AIPAY_DB_PATH", ":memory:")
