# 交易履约审计报告（模板）

- 审计日期：{{date}}
- 审计范围：{{resource_or_store}}
- 数据来源：本地订单库、支付宝 AI 付平台账单、Payment-Proof 流水

## 1. 核验结论
- 核验凭证数：{{verify_total}}
- 通过 / 阻断：{{verify_pass}} / {{verify_block}}
- 阻断违规码分布：{{code_breakdown}}

## 2. 履约与防重放
- 履约流水数：{{fulfillment_count}}
- 重放拦截次数：{{replay_blocked}}
- 幂等命中次数：{{idempotent_hits}}

## 3. 日结对账
- 平台应收（paid 累计）：¥{{settled_total}}
- 差异：bill_only {{bill_only}} ｜ amount_mismatch {{amount_mismatch}} ｜
  status_mismatch {{status_mismatch}} ｜ local_only {{local_only}}
- 是否平衡：{{balanced}}

## 4. 退款初判
- 建议通过 / 人工复核 / 拒绝：{{refund_approve}} / {{refund_review}} / {{refund_reject}}
- 建议退款合计：¥{{refund_total}}

## 5. 风险提示
- 高风险会话：{{high_risk_sessions}}
- 命中规则与证据：{{risk_findings}}

> 本报告由 order-fulfillment-guard 生成，资金状态以支付宝平台记录为最终依据。
