# PPT-maker 文档索引

本文档定义项目文档的层级与唯一职责。出现冲突时，下层文档不得重新定义上层概念；必须引用上层定义，并通过 ADR 记录有意变更。

| 层级 | 文档 | 唯一职责 |
|---|---|---|
| 产品构想 | [`../PPT agent.md`](../PPT%20agent.md) | 定义产品目标、用户价值、功能范围和质量愿景（what / why） |
| 规范设计 | [`superpowers/specs/2026-07-22-ppt-maker-system-design.md`](superpowers/specs/2026-07-22-ppt-maker-system-design.md) | 定义已批准的系统边界、架构、不变量和降级策略（how） |
| 当前产品规格 | [`superpowers/specs/2026-07-27-product-quality-recovery-design.md`](superpowers/specs/2026-07-27-product-quality-recovery-design.md) | 定义两阶段大纲、Deck Blueprint、联网素材及质量恢复；与旧 M2/M3 设计冲突时优先 |
| 总体路线 | [`superpowers/plans/2026-07-22-ppt-maker-roadmap.md`](superpowers/plans/2026-07-22-ppt-maker-roadmap.md) | 定义阶段依赖、工作成果和门禁，不重新定义产品能力 |
| 历史执行计划 | `superpowers/plans/` | 保存已执行或被后续规格替代的逐任务计划（do） |
| 技术决策 | `adr/` | 记录实测后的技术选择、被拒方案、后果和回滚条件 |
| 评测报告 | `evaluations/` | 保存可复现实验结果；不得反向修改产品定义 |

## 引用规则

- “质量优先/速度优先”“资料策略”“成功标准”等产品概念只在产品构想和系统设计中定义；执行计划只引用对应章节。
- M0 未验证的库、模型、解析器、搜索服务和模板策略标为“待验证”，不得写入正式生产依赖。
- 实测结果改变已批准设计时，先写 ADR，再更新系统设计与路线图，最后更新执行计划。
- 代码、测试和报告使用稳定的需求 ID 或 ADR 编号，避免依赖易变化的行号。
- 2026-07-27 之前的 M2/M3 规格保留为历史依据，不再代表当前详细大纲和联网素材流程。
