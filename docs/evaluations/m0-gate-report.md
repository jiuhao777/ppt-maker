# M0 技术验证门禁报告

日期：2026-07-23  
目标环境：Windows 11、Python 3.10.20（conda `AI`）、Microsoft PowerPoint 16.0.15128.20246 x64

## 结论

六项强制机器门禁均已产生独立 JSON 证据并通过。视觉模型与搜索/图片 Provider 属于探索项，当前分别因真实
评测集/资源预算和 Provider Key 缺失而未选型，不阻塞 M1 最小纵向链路。最终人工视觉确认仍需用户打开基线
PPTX 和导出 PNG 后记录结论。

完整测试命令使用项目内隔离临时目录：
`conda run -n AI python -m pytest -v --basetemp=artifacts/pytest-m01-final --junitxml=artifacts/m0/pytest.xml`，
结果为 **116 passed**。
系统默认 pytest 临时目录存在 Windows ACL 拒绝访问，因此未使用；另有 `.pytest_cache` 写入警告，不影响结果。

## 强制证据

| Probe | 复现命令 | 状态 | 关键结果 |
|---|---|---|---|
| PPTX baseline | `python -m pptmaker.m0.pptx_probe` | PASS | 2 页；文本/形状/表格/图片/图表可编辑 |
| PowerPoint Worker | `python -m pptmaker.m0.powerpoint_probe` | PASS | 2 页真实导出；超时后无 owned orphan |
| Geometry | `python -m pptmaker.m0.geometry_probe` | PASS | 4/4 边界与重叠检查 |
| Upload/SSRF | `python -m pptmaker.m0.security_probe` | PASS | 6/6 挑战检查 |
| DeepSeek structured output | `python -m pptmaker.m0.deepseek_probe` | PASS | 20/20 一次通过；P95 2.104 秒 |
| Parser core | `python -m pptmaker.m0.parser_probe` | PASS | Markdown、PPTX 文本和对象定位 3/3 |

所有命令在仓库根目录通过 `conda run -n AI` 执行。最终门禁：
`conda run -n AI python scripts/check_m0_gate.py`。
脱敏机器证据及 SHA-256 清单位于 `docs/evidence/m0/manifest.json`。

## 探索项

- 本地视觉：Harness 6 项测试通过；Qwen3-VL-4B 未加载且未准入，规则检查为默认降级。
- 搜索/图片：统一契约 3 项测试通过；无 Provider Key，因此不发布真实质量排名。
- 动画、复杂模板识别、扫描 PDF/OCR 和视觉自动修复不属于 M1 准入条件。

## 已知风险与变化

- 首版 PowerPoint COM 只支持所有 PowerPoint 窗口已关闭的干净启动；受保护视图和文件占用 UX 仍需实现。
- SSRF 已覆盖协议、解析 IP、重定向和响应边界；生产连接固定使用已验证公网 IP，
  HTTPS 保留原域名 Host、SNI 和证书校验，关闭 DNS TOCTOU。
- PowerPoint Worker 使用请求/输入指纹和幂等日志；相同请求直接重放，冲突键失败关闭。
  导出先写任务临时目录，校验真实页数后原子发布；所有失败路径均按 PID、创建时间和 run ID 清理。
- 用户在 PowerPoint 内手工编辑导出文件不会自动同步回 DSL；重新上传视为新版本并可能丢失语义。
- 共享 `AI` 环境存在预先已有的 `datasets 5.0.0`/`fsspec 2026.6.0` 依赖告警；M0 路径未受影响。
- 开源声明为 Python `>=3.10,<3.13`；本机锁定 3.10.20 仅用于复现。

## M1 进入条件

1. 六项机器门禁必须使用 Schema 2，源码指纹、运行环境、关键指标和证据路径均通过校验；
   完整自动化测试无失败。
2. 以 SlideDSL + Project State 为唯一事实源，完成一次从需求输入到可打开 PPTX 的最小纵向链路。
3. 每个纵向功能同时补最小 Harness、结构化事件和可恢复检查点，不先建设脱离真实链路的大型基础设施。
4. 无搜索 Key、无 GPU、无 PowerPoint 均有明确降级路径；失败页用可见占位页，不阻塞其余页面。

## 人工复核

待用户确认：打开 `artifacts/m0/baseline.pptx`，核对 2 页内容和 PowerPoint 导出 PNG 是否视觉正常。
