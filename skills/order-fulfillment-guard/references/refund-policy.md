# 退款判定规则（refund-policy）

OFG 只输出规则建议（approve / review / reject）与建议退款金额，**真实退款必须由服务端调用
支付宝退款接口并经二次确认**，技能不保存私钥、不直接打款。

## 通用前置规则

1. 退款单 `refund_id` 幂等，重复提交返回首次结论，防止重复退款。
2. 订单不存在 → reject（OFG_1007）；订单已是 refunded → reject（OFG_2003 复核码）。
3. 超过退款窗口（默认 7 天，可按商品覆盖）→ reject（OFG_2001）。

## 分权益类型计算

| 权益类型 | 未使用 | 部分使用 | 已耗尽/到期 |
|---|---|---|---|
| 一次性买断 one_off | 未核销 → 全额退 | 已交付 → review（数字商品默认不全退，人工判定） | review/reject |
| 次数包 count_pack | 全额退 | 按剩余比例：`实付 × (total-used)/total` | reject（OFG_2002） |
| 时长包 duration | 按剩余天数比例退 | 同左，依 `valid_until` 计算 | 到期 reject（OFG_2002） |

金额统一四舍五入到分（`ROUND_HALF_UP`）。所有结论都带原因文案与 OFG 码，可直接写进客服工单。
