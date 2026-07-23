# ADR 0001：PPTX 生成与 PowerPoint 渲染

## 状态

接受（M0）

## 背景与实测

首版面向 Windows 11 + Microsoft PowerPoint。`python-pptx` 基线生成了包含文本、形状、表格、图片和图表的
2 页可编辑文件。独立 STA Worker 用 PowerPoint COM 导出 2 页图片，并在硬超时实验后确认没有遗留其拥有的
PowerPoint 进程。机器证据位于 `artifacts/m0/pptx-baseline.json` 和 `artifacts/m0/powerpoint-worker.json`。

## 决策

以 `python-pptx` 生成 `.pptx`，以单个、串行、STA 的独立 Worker 调用 PowerPoint 完成真实渲染。
SlideDSL + Project State 是唯一事实源，PPTX 是产物。Worker 通过输入和请求指纹实现幂等重放，
冲突键失败关闭；任务专属目录中先写临时输出，验证真实页数与顺序后原子发布。

## 拒绝方案

- 只依赖 LibreOffice：不能代表目标 PowerPoint 的实际渲染。
- 在 Web 进程内直接运行 COM：卡死会拖垮主流程且难以清理进程。
- 自动接管用户已有 PowerPoint 实例：存在误关用户文档风险。

## 后果与回滚触发

首版要求干净环境启动且用户关闭 PowerPoint 窗口；无 PowerPoint 时降级为仅生成文件、不提供真实预览。
受保护视图、文件占用提示和业务流程检查点将在纵向链路中补齐。若目标 Office 版本的打开成功率
无法达到 100% 或出现误杀用户进程，停止 COM 默认启用并回退到仅生成模式。
