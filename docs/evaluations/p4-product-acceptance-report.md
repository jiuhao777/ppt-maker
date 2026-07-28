# P4 产品验收门禁报告

日期：2026-07-28

## 自动化结果

- 离线回归：450 passed，6 deselected。
- P4 门禁：通过。
- 历史门禁：M1、M2、M3、P1、P2、P3 全部通过。
- 代表性 10 页 Deck Blueprint 已完成编译、质量检查、PPTX 构建和 python-pptx 重新打开。

## 量化结果

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 需求覆盖率 | 100% | ≥90% |
| 结论标题保留率 | 100% | ≥90% |
| 严重几何缺陷 | 0 | 0 |
| 正文密度违规率 | 0% | ≤5% |
| 公共事实可追溯率 | 100% | ≥95% |
| 图片归因率 | 100% | 100% |
| PPTX 重新打开 | 成功 | 100% |

机器可读证据位于 `artifacts/p4-product-acceptance/pytest.xml` 和 `metrics.json`。

## 隔离验收

Office、DeepSeek、博查和公网图片检查不计入离线通过。当前 Codex 进程没有可用的交互式 Office 登录会话，因此 Office COM 测试需在用户 CMD 中运行。M0 的离线四项 Probe 已刷新；PowerPoint Worker 与 DeepSeek Probe 需按 `docs/manual-acceptance.md` 刷新后，M0 总门禁才会重新转为通过。

## 结论

P4 离线产品门禁通过。代码阶段没有已知阻塞缺陷；最终成品验收只剩用户计划中的真实 Key、联网和 Windows PowerPoint 人工检查。
