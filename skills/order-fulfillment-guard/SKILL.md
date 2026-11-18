---
name: order-fulfillment-guard
version: 0.1.0
description: >-
  AI 交易履约核验官（Order Fulfillment Guard，简称 OFG）。当需要核对支付宝 AI 付 Payment-Proof
  支付凭证、校验订单与交付一致性、核销买断/次数包/时长包权益、做平台账单日结对账、判定退款申请、
  或排查重复支付与薅羊毛风险时使用。触发语义包括：核验支付凭证、验证 402 支付、订单核销、权益发放、
  日结对账、账单差异、退款判定、重复扣款、防重放、交易风控、Payment-Proof、amtPaymentLink、
  out_trade_no、trade_no、resource_id。面向独立开发者与小团队，输出结构化 JSON 结论，可直接进审计流。
license: MIT
entrypoint: python3 -m scripts.ofg.cli
runtime: python>=3.10
pricing:
  track: Skill Pay
  models:
    - name: 单次买断
      price_cny: 19.9
      note: 交付全部技能明文，本地运行，数据不出端
    - name: 按次调用
      price_cny: 0.5
      note: 通过 Skill 市场按次计费，不自动续费
---

# Order Fulfillment Guard · AI 交易履约核验官

把「拉起支付之后」的事做对：**凭证核验 → 权益核销 → 日结对账 → 退款判定 → 风险信号**。
本技能只做判定与留痕，不替你向支付宝发起真实扣款/退款动作，所有资金操作都输出可复核的建议与证据。

## 何时使用

- 收到买家（人或 Agent）回传的 `Payment-Proof`，需要判断这笔钱能不能放心发货；
- 需要把一次性买断、次数包、时长包三类权益做幂等核销，防止重试/重放重复发放；
- 每天关店前，要把本地订单和平台账单逐笔核对，快速定位差异；
- 客服收到退款申请，要先按规则给出"自动通过 / 人工复核 / 拒绝"的初判和依据；
- 怀疑存在重复支付、金额篡改、会话不一致等薅羊毛行为，需要风控打分。

## 输入约定

- 订单与凭证使用 UTF-8 JSON 文件（样例见 `examples/`）；也可通过 stdin 传入 JSON。
- 金额一律使用字符串十进制（如 `"9.90"`），内部以 `Decimal` 处理，禁止浮点比较。
- 凭证结构对齐支付宝 AI 付 Machine Pay：`payment_proof / trade_no / client_session`，业务侧另带
  `out_trade_no / amount / resource_id / active`。

## 标准工作流

1. **核验（verify）**：解析凭证并执行五要素校验——`active=true`、金额一致、商户订单号一致、
   资源 ID 一致、`trade_no` 未被使用（防重放）。任一不通过即拒绝交付并给出违规码。
2. **核销（entitle）**：核验通过后按权益类型幂等发放；同一 `fulfillment_id` 重复调用结果不变。
3. **对账（reconcile）**：本地订单 ↔ 平台账单逐笔匹配，输出四类差异并附金额影响。
4. **退款（refund）**：按权益已用情况与退款窗口给出初判，不直接打款。
5. **风控（risk）**：对一批订单做规则评分，输出高风险会话与命中规则。

## 命令索引

```bash
# 1. 凭证核验（人读报告加 --pretty）
python3 -m scripts.ofg.cli verify --proof examples/proof.sample.json --order examples/orders.sample.json --pretty

# 2. 权益核销（one_off / count_pack / duration）
python3 -m scripts.ofg.cli entitle --db ./ofg.db --proof examples/proof.sample.json --order examples/orders.sample.json

# 3. 日结对账
python3 -m scripts.ofg.cli reconcile --local examples/orders.sample.json --bill examples/platform-bill.sample.json --pretty

# 4. 退款初判
python3 -m scripts.ofg.cli refund --db ./ofg.db --request examples/refund-request.sample.json --pretty

# 5. 风控扫描
python3 -m scripts.ofg.cli risk --order examples/orders.sample.json --pretty
```

所有命令默认向 stdout 输出 JSON，便于被 Agent/流水线消费；`--pretty` 输出人读格式，退出码
`0=通过/无高危`、`2=存在阻断或高危`、`1=输入或系统错误`。

## 深入参考（按需读取，不要一次性加载）

- `references/verification-rules.md`：五要素核验规则、违规码与防重放实现细节
- `references/reconciliation.md`：对账口径、四类差异定义与处理建议
- `references/refund-policy.md`：三类权益的退款计算公式与人工复核边界
- `templates/audit-report.md`：审计报告模板，可把 JSON 结论贴入后交付客服/财务

## 安全边界

- 不内置任何商户私钥/Token，不发起真实网络支付；真实环境请在网关层调用支付宝官方
  `alipay.aipay.agent.payment.precreate / verify`，本技能负责其结果的业务侧复核。
- 只读输入文件、只写显式指定的 `--db` 数据库；默认拒绝在仓库目录之外写文件。
