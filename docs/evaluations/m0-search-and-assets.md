# M0 搜索与素材服务评测

## 结论

M0 已建立可复现的 JSONL Runner，以及带来源页、作者、访问日期、许可证名称、许可证 URL 和
许可证状态的统一契约。当前没有配置搜索或图片服务 Key，因此没有伪造中文相关性、时延和稳定性分数，
默认 Provider 暂不选定；正式产品路径在无 Key 时关闭联网研究，只允许用户提交明确网页 URL。

## 候选与条款核验（2026-07-23）

| 类别 | 候选 | 已确认 | 尚未验证 | 结论 |
|---|---|---|---|---|
| 搜索 | 博查 AI Search | 有面向搜索 API 的产品文档 | 中国网络实测、固定查询质量、限流、成本 | 候选，需 Key 后评测 |
| 搜索 | Tavily Search | Bearer Key；支持 China country boost；basic/fast 每次 1 credit | 中国网络可达性和中文官方来源排名 | 候选，需 Key 后评测 |
| 图片 | Pexels API | 免费内容；API 展示结果时要求明显回链，建议署名摄影师；存在独立许可证限制 | 中国网络可达性和中文查询召回 | 优先候选，需 Key 后评测 |
| 图片 | Pixabay API | API Key；默认 100 次/60 秒；要求在搜索结果处展示来源；使用 Pixabay Content License | 中国网络可达性和中文查询召回 | 备选，需 Key 后评测 |

官方资料：

- 博查 API 产品文档：https://mkp-res.hc-cdn.com/marketplace/public/appv2/attachment/FE5/A96/96F/0000000000FE5A9696F.20250527042304.feac985174234808a69f64e899bd6792.pdf
- Tavily Search：https://docs.tavily.com/documentation/api-reference/endpoint/search
- Pexels API：https://www.pexels.com/api/documentation/
- Pexels License：https://www.pexels.com/legal-pages/license/
- Pixabay API：https://pixabay.com/api/docs/
- Pixabay Content License：https://pixabay.com/service/license-summary/

## 固定评测协议

获得 Key 后，对每个搜索 Provider 逐一运行 10 个冻结查询、每个查询 3 次，保存原始标准化结果、
时延、域名数、重复 URL 和错误。人工只对每次前五条结果评中国语境相关性。图片 Provider 还必须验证
MIME、像素尺寸、作者字段、来源页和许可证快照；下载内容仍经过 SSRF 与文件安全门禁。

## 失败关闭与宽松素材模式

- 未配置搜索 Key：联网研究关闭，不启用非保证抓取作为正式降级。
- 搜索无结果：提示用户切换宽松素材模式或手动提供 URL。
- 宽松素材模式：允许许可证状态为 `unknown/restricted` 的候选进入人工确认队列，但必须显示原链接、
  作者（若可得）和风险提示；未经确认不得自动进入最终 PPT。
- 网页数据永远先提取、净化、事实化并存入 Fact Store，不能直接拼接到 Agent System Prompt。
