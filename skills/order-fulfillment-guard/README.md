# order-fulfillment-guard · 交易履约核验官（Skill Pay 方案）

PAYATHON 2026 参赛作品 · Skill Pay 赛道。解决 AI 交易"收款之后"的可信履约问题：
**凭证核验 → 权益核销 → 日结对账 → 退款初判 → 风控信号**，纯 Python 标准库实现，可离线运行、数据不出端。

## 它解决什么真问题

社区调研显示开发者的痛点不在拉起支付，而在支付之后：订单状态查不到、重试导致重复发货、
金额被篡改、退款无据可依、平台账单对不平。本技能把官方 `verify` 之后的业务校验固化成可复用规则，
让独立开发者不必自建交易中台。

## 目录结构

```
order-fulfillment-guard/
├── SKILL.md                 # 技能入口（触发语义 + 工作流 + 命令索引）
├── manifest.json            # 上架元数据与 Skill Pay 计费方案
├── requirements.txt         # 零第三方依赖
├── scripts/ofg/
│   ├── cli.py               # 命令行入口
│   ├── models.py            # 领域模型与 OFG 违规码
│   ├── proof.py             # Payment-Proof 五要素核验
│   ├── entitlement.py       # 一次性/次数/时长权益幂等核销
│   ├── store.py             # SQLite 账本（防重放、权益、退款）
│   ├── reconcile.py         # 日结对账（四类差异）
│   ├── refund.py            # 退款规则引擎（只建议不打款）
│   └── risk.py              # 可解释风控规则
├── references/              # 按需加载的规则详解
├── templates/audit-report.md
├── examples/                # 可直接运行的样例 JSON
└── tests/                   # 19 个 unittest 用例
```

## 快速开始

```bash
# 无需安装依赖，Python 3.10+
python3 -m scripts.ofg.cli verify \
  --proof examples/proof.sample.json --order examples/orders.sample.json --pretty

python3 -m scripts.ofg.cli reconcile \
  --local examples/orders.sample.json --bill examples/platform-bill.sample.json --pretty

python3 -m scripts.ofg.cli risk --order examples/orders.sample.json --pretty
```

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

## 退出码约定（便于接入 CI/客服流水线）

- `0`：通过 / 无高危
- `2`：存在阻断性违规或高危风险（如重放、金额不符、高风险会话、对账不平）
- `1`：输入或系统错误

## 与 Agent 层方案的关系

姊妹项目 `services/aipay-402-gateway` 负责机器侧实时 402 收款与自动履约；本技能面向人和运营侧，
做事后核验、对账与退款初判。两者共用 `out_trade_no / trade_no / resource_id / Payment-Proof`
协议词汇与同一套五要素核验规则。

## 安全边界

不内置私钥、不发起网络支付、不直接退款；所有资金动作仅产出带证据链的 JSON 建议。
