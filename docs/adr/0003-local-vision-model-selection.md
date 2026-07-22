# ADR 0003：本地视觉模型

## 状态

暂不选型；探索项不阻塞 M1

## 背景与实测

M0 建立了固定 Prompt、严格 Schema、逐页 Runner、指标和显存采样接口。当前只有 5 张合成 Harness 样例。
本地 Qwen3-VL-4B-Instruct 权重约 8.88 GB，超过 8 GB 显卡的 6.5 GiB 安全预算，且受控 4-bit 运行时未安装，
因此加载前即安全阻断。证据见 `artifacts/m0/vision-model-resource.json` 和
`docs/evaluations/m0-vision-models.md`。

## 决策

视觉检查默认关闭并标记“研究预览”；M1 使用几何与规则检查。正式准入需至少 20 张真实 PowerPoint 渲染页，
召回率 ≥70%、误报率 ≤20%、JSON 有效率 ≥95%，并在资源预算内逐模型串行运行。

## 拒绝方案

- 强行 BF16/CPU Offload 加载 4B 模型：不能代表目标 GPU 体验且有 OOM 风险。
- 用 5 张合成图直接选型：无法衡量真实 PPT 的视觉语义和误报。

## 后果与回滚触发

无 GPU 或模型 OOM 时自动降级到规则检查并提示用户视觉检查已跳过。任何模型在挑战集上超过误报门槛，
都撤回自动修复权限，仅保留建议模式。
