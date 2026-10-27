# 项目归档说明

本文档在项目停止开发时编写，用于在本地目录被删除后仍能完整还原这个项目：
记录终止原因、最终状态、仓库结构，以及**所有未纳入 Git 的大文件清单和重新获取方式**。

## 1. 归档结论

| 项目 | 值 |
|---|---|
| 项目名 | ppt-maker |
| 定位 | 本地优先的 AI 演示文稿（PPT）生成 Agent，面向 Windows 11 + Microsoft PowerPoint |
| 状态 | **已终止**，未达成可交付的产品效果 |
| 最终提交 | `1c9ee64` — `fix: call DeepSeek through direct HTTP` |
| 归档时已跟踪文件 | 279 个，约 1.18 MB |
| 未纳入 Git 的大文件 | `models/` 共 12.26 GB / 55 个文件（详见第 4 节） |

## 2. 为什么停止

项目从 2026-07-21 起共进行 8 个工作日（详见根目录 [`ppt-maker.txt`](../ppt-maker.txt) 时间表），
走完了 M0–M3 与 P1–P4 的流程，但最终没有通过产品验收：

- **生成质量不达标**：早期大纲过于简略，生成的 PPT 效果很差；后期重做为「详细 Deck Blueprint」
  （逐页结论、内容层级、排版、配图用途与位置、演讲备注、页间承接），质量仍未达到可用标准。
- **实现问题反复**：出现过无法生成 PPT、图片检索失败等阻塞缺陷；更换模型（DeepSeek ↔ Codex）后
  修复效率依然很低。
- **选题本身被否定**：指导老师认为「做 PPT 的 Agent」同质化严重，建议重新选题 —— 这是项目终止的
  直接原因，而非单纯的工程问题。

因此本仓库保留的是**一个失败项目的完整过程记录**，包括设计规格、执行计划、技术决策（ADR）、
评测报告与验收证据。代码可以运行，但不保证产出可用的演示文稿。

## 3. 仓库结构

```
ppt-maker/
├── PPT agent.md              # 产品构想：目标、用户价值、功能范围、质量愿景（what/why）
├── ppt-maker.txt             # 逐日开发时间表（项目过程的一手记录）
├── README.md                 # 使用说明与能力边界
├── pyproject.toml            # 依赖与打包（Python 3.10–3.12）
├── src/pptmaker/             # 源码
│   ├── ui/app.py             # Streamlit 界面入口
│   └── ...                   # 解析、大纲、检索、Blueprint、PPTX 生成、校验等模块
├── tests/                    # pytest 测试集
├── scripts/                  # 各阶段门禁校验脚本（M0–M4 / P1–P4）
├── docs/
│   ├── README.md             # 文档分层规则（唯一职责约定）
│   ├── ARCHIVE.md            # 本文件
│   ├── adr/                  # 技术决策记录（渲染、解析器、视觉模型、搜索与素材）
│   ├── evaluations/          # 各阶段评测报告与门禁结论
│   ├── evidence/             # 门禁证据 JSON
│   ├── superpowers/specs/    # 系统设计与各阶段规格
│   ├── superpowers/plans/    # 逐任务执行计划（含被替代的历史计划）
│   └── manual-acceptance.md  # 人工验收清单
├── artifacts/                # 实验与验收原始证据（pytest XML、评估 JSON、样本文件）
├── benchmarks/               # 基准测试
├── requirements/             # 依赖清单
└── models/                   # 本地模型权重（12.26 GB，未纳入 Git）
```

## 4. 未纳入 Git 的大文件（重要）

`models/` 目录总计 **12.26 GB / 55 个文件**，全部被 [`.gitignore`](../.gitignore) 的 `/models/` 规则排除。
GitHub 对单文件有 100 MB 硬限制，这些权重无法入库，也无法用普通 Git 追踪（需要 Git LFS 或对象存储）。

| 目录 | 模型 | 体积 | 文件数 | 在项目中的作用 | 上游来源 |
|---|---|---|---|---|---|
| `QwenQwen3-VL-4B-Instruct/` | Qwen3-VL-4B-Instruct（视觉语言模型） | 8.28 GB | 14 | 幻灯片渲染页的视觉质量检查（研究预览，默认关闭） | [`Qwen/Qwen3-VL-4B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) |
| `HY-MT1.5-1.8B/` | Hunyuan-MT 1.5 1.8B（翻译模型，33 语种互译） | 3.81 GB | 11 | 多语言内容翻译 | [`tencent/HY-MT1.5-1.8B`](https://huggingface.co/tencent/HY-MT1.5-1.8B) · [ModelScope](https://modelscope.cn/collections/Tencent-Hunyuan/HY-MT15) |
| `bge-small-qq-qa/` | bge-small-qq-qa（句向量，512 维） | 0.09 GB | 12 | 语义检索 / 素材相关性排序 | [`svjack/bge-small-qq-qa`](https://huggingface.co/svjack/bge-small-qq-qa) |
| `models--sentence-transformers--all-MiniLM-L6-v2/` | all-MiniLM-L6-v2（句向量） | 0.09 GB | 18 | 语义检索后备嵌入 | [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |

最后一个目录是 Hugging Face 的原生缓存结构（`blobs/` + `refs/` + `snapshots/`），
其余三个是直接下载的模型目录。

### 重新获取

Hugging Face：

```bat
pip install -U "huggingface_hub[cli]"
huggingface-cli download Qwen/Qwen3-VL-4B-Instruct --local-dir models/QwenQwen3-VL-4B-Instruct
huggingface-cli download tencent/HY-MT1.5-1.8B   --local-dir models/HY-MT1.5-1.8B
huggingface-cli download svjack/bge-small-qq-qa  --local-dir models/bge-small-qq-qa
```

ModelScope（国内网络更稳）：

```bat
pip install -U modelscope
modelscope download --model Qwen/Qwen3-VL-4B-Instruct --local_dir models/QwenQwen3-VL-4B-Instruct
modelscope download --model Tencent-Hunyuan/HY-MT1.5-1.8B --local_dir models/HY-MT1.5-1.8B
```

### 关于视觉模型的实测结论

M0 阶段实测：Qwen3-VL-4B 权重约 8.88 GB，超过 8 GB 显卡设定的 6.5 GiB 安全预算，
且受控 4-bit 运行时未安装，因此**在加载前即被资源守卫阻断**，从未真正参与过质量判定。
详见 [`adr/0003-local-vision-model-selection.md`](adr/0003-local-vision-model-selection.md) 与
[`evaluations/m0-vision-models.md`](evaluations/m0-vision-models.md)。
结论是：视觉检查保持「研究预览 / 默认关闭」，生产链路只使用几何与规则检查。

## 5. 其他未纳入 Git 的内容

| 路径 | 体积 | 说明 | 是否需要保留 |
|---|---|---|---|
| `models/` | 12.26 GB | 模型权重，见第 4 节 | 可重新下载，不必保留 |
| `.playwright-cli/` | 14.5 MB | Playwright 浏览器临时缓存 | 否，可再生 |
| `.pytest_cache/` | 很小 | pytest 缓存 | 否 |
| `.superpowers/`、`.reasonix/`、`.agents/`、`.streamlit/` | ≤0.01 MB | 工具链运行时状态 | 否 |
| `.tmp/` | 0 | 空目录 | 否 |
| `projects/` | — | 用户生成的项目数据（运行时产生），归档时不存在 | 否 |
| `.env` | — | 本地密钥（从未入库，归档时不存在） | 否 |

`.gitignore` 还全局排除了二进制产物：`*.pptx`、`*.pdf`、`*.docx`。
`artifacts/` 下的评测证据（pytest XML、评估 JSON、渲染 PNG）已在归档时单独纳入版本控制，
但其中的 `.pptx` / `.docx` / `.pdf` 样本受该规则限制，未入库。

## 6. 恢复运行

```bat
conda activate AI
pip install -e ".[test]"
set PYTHONIOENCODING=utf-8
streamlit run src/pptmaker/ui/app.py
```

配置仅有一个示例文件 [`.env.example`](../.env.example)，指向 DeepSeek：

```
DEEPSEEK_API_KEY=replace-in-local-environment-only
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

API Key 只保存在当前 Streamlit 会话中，刷新即丢失，不写入 SQLite、导出文件或日志。

## 7. 已知未完成 / 失败点

- 生成质量未达可用标准，是项目终止的核心问题。
- 视觉质量检查只有评测框架（5 张合成样例），从未在真实 PowerPoint 渲染页上定标
  （正式准入需 ≥20 张真实页面、召回率 ≥70%、误报率 ≤20%、JSON 有效率 ≥95%）。
- 导出后在 PowerPoint 里的人工修改不会同步回 Blueprint。
- 明确不支持：WPS、macOS/Linux 下的 PowerPoint 自动化、云端部署。

---

编写于项目归档时。本文件随仓库一同保留，作为这个失败项目的收尾记录。