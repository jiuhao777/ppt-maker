# M3 页面 DSL、AI 内容生成与基础 PPT Builder 设计

## 1. 目标

M3 建立从 M2 产出的批准大纲到可编辑 `.pptx` 文件的端到端流程：

```
DeckOutline（M2批准版本）
  → Content Planner（AI 页面文案展开）
  → Design Planner（AI 主题/色彩/字体决策）
  → SlideSpec[]（页面 DSL）
  → PPT Builder（确定性 python-pptx 引擎）
  → .pptx 文件
  → PowerPoint 渲染（缩略图）
  → 页面展示 + 用户下载
```

M3 的完成边界是：

- 用户批准的大纲可以一键生成完整 `.pptx`；
- 文件可在 Microsoft PowerPoint 中正常打开；
- 所有文字、形状、表格保持原生可编辑；
- 不存在元素严重越界或重叠；
- 页面缩略图可在 Streamlit 中查看；
- 用户可通过按钮下载 `.pptx`。

## 2. 输入边界

M3 接收：

- M2 产出的 `DeckOutline`（含每页 title、objective、key_points、page_type、source_locations、gaps）；
- M2 产出的 `RequirementBrief`（含 purpose、audience、style、task_type 等）；
- M2 材料片段 `MaterialChunk[]`（用户上传的原始材料文本）；
- M2 联网事实 `FactRecord[]`（博查核验结果，已被排除的来源不出现在输入中）。

不接收图片、扫描 PDF、外部网页原始内容或用户模板。

## 3. 输出

- 可编辑 `.pptx` 文件；
- PowerPoint 渲染的单页 PNG 缩略图；
- 生成配置记录（色彩方案、字体选择）；
- 每页 DSL 的 JSON 记录（便于后续评测和修复）。

## 4. 技术方案

### 4.1 总体流程

```
DeckOutline + RequirementBrief + MaterialChunk[] + FactRecord[]
        │
        ▼
  Design Planner（单次 LLM 调用 / 用户选择预设）
        │  根据 task_type/audience/style → 色彩方案 + 字体 + 布局偏好
        │  产出: DesignPlan { palette, fonts, layout_hints }
        ▼
  Content Planner（单次 LLM 调用）
        │  结合视觉风格展开每页 title/objective/key_points → 完整文案
        │  产出: ContentPlan { slides: [SlideContent] }
        ▼
  Spec Compiler（确定性）
        │  ContentPlan + DesignPlan → SlideSpec[]
        │  计算元素位置、尺寸、层级；执行溢出检测
        ▼
  PPT Builder（确定性 python-pptx）
        │  SlideSpec[] → Presentation 对象 → .pptx 写入
        │  字体回退链执行
        ▼
  PowerPoint Renderer（M0已验证）
        │  .pptx → PNG 缩略图
        ▼
  Streamlit 展示（缓存缩略图） + 下载按钮
```

### 4.2 Design Planner（先于内容生成）

**为什么先于内容**：视觉风格（如"极简干净"vs"创意活力"）直接影响内容的表达方式和信息密度。先定风格再写文案，避免视觉与内容脱节。

**风格预设**：UI 提供 5 种常见风格 + 1 种自动判断：

| 预设 | 配色特征 | 适用场景 |
|------|----------|----------|
| 商务专业 | 深蓝 + 白 + 金 | 工作汇报、项目汇报、商业路演 |
| 学术严谨 | 藏青 + 浅灰 + 蓝 | 学术答辩、数据报告 |
| 创意活力 | 橙 + 白 + 深灰 | 活动宣讲、创意提案 |
| 极简干净 | 黑 + 白 + 浅灰 | 通用、课件、内部讨论 |
| 科技未来 | 深紫渐变 + 白 + 青 | 技术分享、产品发布 |
| 自动判断 | 由 AI 根据 task_type 决定 | 用户不确定时 |

用户选择预设时，Design Planner 直接用预设色彩和字体，不调用 LLM。选择"自动判断"时，调用 LLM 生成自定义 DesignPlan。

**输入**：RequirementBrief（task_type、audience、style）、用户选择的 `style_preset`

**输出**：`DesignPlan`

```python
class ColorPalette(BaseModel):
    primary: str       # 主色 hex
    secondary: str     # 辅色 hex
    accent: str        # 强调色 hex
    background: str    # 背景色 hex
    text_primary: str  # 主文字色 hex
    text_secondary: str # 次文字色 hex


class FontSet(BaseModel):
    title_zh: str       # 标题中文字体（默认 "微软雅黑"）
    body_zh: str        # 正文中文字体（默认 "微软雅黑"）
    title_en: str       # 标题英文字体（默认 "Arial"）
    body_en: str        # 正文英文字体（默认 "Arial"）
    title_size: int     # 标题字号 pt（默认 30）
    subtitle_size: int  # 副标题字号 pt（默认 20）
    body_size: int      # 正文字号 pt（默认 16）


class DesignPlan(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str
    preset: str                   # 使用的预设名称 或 "custom"
    palette: ColorPalette
    fonts: FontSet
    style_notes: str              # 风格说明（≤200字）
```

**约束**：

- 主色与背景色对比度 ≥ 4.5:1（WCAG AA）；
- 标题字号 ≥ 24pt，正文字号 ≥ 14pt；
- 预设模式下不调用 LLM，直接返回预设常量；
- 自动判断模式调用 LLM，初次校验失败允许一次修复重试。

### 4.3 Content Planner（在 Design Planner 之后）

**输入**：DeckOutline、MaterialChunk[]、FactRecord[]、DesignPlan（视觉风格已确定）

**输出**：`ContentPlan`

```python
class SlideContent(BaseModel):
    page_id: str                     # 对应 OutlinePage.id
    title: str                       # 页面标题（≤40字）
    subtitle: str | None             # 副标题或上下文说明
    body_paragraphs: list[str]       # 正文段落（每条≤200字）
    bullet_points: list[str]         # 要点（如适用）
    key_number: str | None = None    # [M5预留] 核心数字或指标，当前版本不渲染
    key_number_label: str | None = None  # [M5预留] 数字说明
    image_suggestion: str | None     # 建议配图方向（M5 使用）
    source_references: list[str]     # 来源引用（来自 FactRecord.source_title）


class ContentPlan(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str
    outline_version: int             # 对应 DeckOutline.version
    slides: list[SlideContent]
```

**约束**：

- 必须覆盖大纲所有页面，不增不减；
- 必须引用 verified_facts 中的来源而非编造数据；
- 模型记忆与联网事实冲突时以联网事实为准；
- 无法确认的事实标注 `[待验证]`；
- 结合 DesignPlan 的视觉风格调整信息密度（如极简风格正文更短）；
- 初次 Schema 校验失败允许一次修复重试，再次失败进入 `FAILED_RECOVERABLE`。

**页级重试机制**：

Content Planner 失败不按页单独重试（单次 LLM 调用覆盖所有页面），但如果整体 Schema 校验失败，第一次修复重试时会将失败页面详情传给模型，让模型针对性修正。两次全量失败后进入 `FAILED_RECOVERABLE`，保留已生成的 ContentPlan（如有）供后续排查。

### 4.4 SlideSpec（页面 DSL）

```python
class TextElement(BaseModel):
    type: Literal["text"]
    text: str
    x: float    # Inches
    y: float    # Inches
    width: float
    height: float
    font_size: int
    font_name: str
    bold: bool = False
    color: str  # hex


class BulletElement(BaseModel):
    type: Literal["bullet"]
    items: list[str]
    x: float
    y: float
    width: float
    height: float
    font_size: int
    font_name: str
    color: str


class ImagePlaceholder(BaseModel):
    type: Literal["image_placeholder"]
    x: float
    y: float
    width: float
    height: float
    description: str    # 建议配图描述（M5 替换为实际图片）


class RectShape(BaseModel):
    type: Literal["rect"]
    x: float
    y: float
    width: float
    height: float
    fill_color: str     # hex


class TableBlock(BaseModel):
    type: Literal["table"]
    rows: list[list[str]]
    x: float
    y: float
    width: float
    height: float
    font_size: int


SlideElement = TextElement | BulletElement | ImagePlaceholder | RectShape | TableBlock


class SlideSpec(BaseModel):
    page_id: str
    order: int
    page_type: str              # cover / contents / section / content / ending
    background_color: str
    elements: list[SlideElement]
```

### 4.5 Spec Compiler（确定性布局引擎）

**输入**：ContentPlan + DesignPlan  
**输出**：SlideSpec[]

**布局规则**（确定性，不调用 LLM）：

| page_type | 布局 |
|-----------|------|
| cover | 标题居中 + 副标题下方 + 底部装饰线 |
| contents | 编号列表 + 每项左侧装饰条 |
| section | 章节号大字体 + 章节标题 |
| content | 顶部标题栏 + 正文区（支持双栏） + 底部来源标注 |
| ending | 居中致谢/总结文字 |

**约束**：

- 画布 = 16:9（13.333" × 7.5"）；
- 标题栏固定高度 1.0" 位于顶部；
- 正文区域起始于 y=1.3"；
- 安全边距：左右 ≥ 0.7"，上下 ≥ 0.5"；
- 元素之间间距 ≥ 0.15"；
- 正文单行不超过画布宽度（自动换行由 python-pptx 处理）；
- 图片占位区域最大 5.0" × 3.5"（M5 替换）；
- 每页元素不超过 10 个。

**内容溢出检测与处理**（Spec Compiler 输出前执行）：

对于正文元素，估算文本是否超出文本框容量（按字号 × 行数 × 行高估算）。检测到溢出时，按以下顺序处理：

1. **缩减字号**：在 ≥12pt 范围内逐步缩小直到文本适配；
2. **压缩内容**：通过模型调用截断多余句子（仅取前 N 句能适配的），加"…"标记，同时保留来源引用；
3. **移至下页**：当前页是 content 类型且后续有空页时，溢出内容移到新页面；
4. **标记截断**：无法移页时在文本末尾加"⚠ 内容溢出，请手动调整"标记。

溢出处理完成后重新验证所有元素仍在安全边距内。

### 4.6 PPT Builder

**输入**：SlideSpec[] + DesignPlan  
**输出**：`.pptx` 文件路径

**字体回退链**：

PT Builder 在设置字体时必须使用 `choose_font()` 函数：

```python
FONT_FALLBACK = {
    "zh": ["微软雅黑", "SimHei", "Microsoft YaHei", "Arial"],
    "en": ["Arial", "Calibri", "Segoe UI", "sans-serif"],
}

def choose_font(requested: str, lang: str) -> str:
    # 依次尝试请求的字体和回退链，返回第一个系统存在的字体
    # 最终必定返回 "Arial"（Windows 必存在）
```

**职责**：

- 创建 16:9 Presentation；
- 逐页创建空白 slide（layout 6 = blank）；
- 按 SlideSpec.elements 依次添加 python-pptx 元素；
- 所有文本使用 `text_frame.word_wrap = True`；
- 形状使用 DesignPlan 中定义的颜色；
- 不调用任何 LLM。

### 4.7 PowerPoint 渲染与缩略图缓存

复用 M0 已验证的 `pptmaker.powerpoint.client.render_with_timeout`：

- 输入：`.pptx` 路径 + 输出目录；
- 输出：每页一张 PNG；
- 超时 60 秒，渲染锁保护；
- 失败不阻塞文件下载。

**缩略图缓存**：生成后 PNG 路径存入 `st.session_state`，页面刷新时直接读取缓存路径，不重复读取磁盘或重新渲染。

### 4.8 Streamlit UI

在项目工作区大纲审批后新增：

- **风格选择器**：6 个选项（商务专业/学术严谨/创意活力/极简干净/科技未来/自动判断），默认"自动判断"；
- **"生成 PPT"按钮**：触发 Design Planner → Content Planner → Spec Compiler → PPT Builder → 渲染；
- **生成进度**：显示阶段文字（设计风格中 / 规划内容中 / 构建文件中 / 渲染缩略图中）；
- **缩略图区域**：生成完成后展示每页缩略图（`st.image` grid，来自缓存）；
- **下载按钮**：`st.download_button` 下载 `.pptx`（文件内容也缓存到 session_state）；
- **错误处理**：生成失败显示安全错误消息，保留大纲状态不变。

## 5. 数据持久化

- `ContentPlan` 和 `DesignPlan` 写入 SQLite（沿 M2 模式）；
- `SlideSpec[]` 序列化 JSON 存入项目目录 `projects/{id}/specs/`；
- `.pptx` 保存到 `projects/{id}/exports/{outline_version}/`；
- 缩略图保存到 `projects/{id}/renders/{outline_version}/`。

## 6. 错误处理

- 模型结构化输出校验失败：一次修复重试，再失败转为 `FAILED_RECOVERABLE`；
- PPT Builder 异常：保留已生成的 `.pptx`（如有），显示安全错误；
- PowerPoint 渲染失败：标记渲染不可用，但不阻塞下载；
- API Key 缺失：暂停需要模型的动作，不清除状态，提示用户。

## 7. 非目标

M3 不实现：

- 样张审批和选择性生成（M4）；
- 并行页面生成（M4）；
- 质量评测与自动修复（M6）；
- 自然语言局部修改和版本回退（M7）；
- 复杂图表（柱状图、折线图、饼图）、时间轴、流程图（M5/M8）；
- 用户自定义模板和主题继承（M8）；
- 图片搜索和图库集成（M5）；
- 演讲备注写入；
- 动画、SmartArt、宏。

## 8. 测试与验收

自动化测试覆盖：

- ContentPlan / DesignPlan / SlideSpec / SlideElement Schema；
- Content Planner 必须覆盖所有大纲页面；
- Design Planner 色彩对比度 ≥ 4.5:1；
- Spec Compiler 元素不越界（复用 M0 geometry.out_of_bounds）；
- Spec Compiler 元素之间无严重重叠（overlap_ratio < 0.2）；
- PPT Builder 产出文件可用 python-pptx 重新打开，页数匹配；
- PowerPoint 渲染产出预期数量的 PNG；
- API Key 不进入任何持久化数据。

验收标准：

- 生成 8–15 页 `.pptx` 文件可正常打开；
- 所有文本、形状可编辑；
- 无元素越界（安全边距内）；
- 无严重遮挡（overlap_ratio < 0.2）；
- 缩略图可正确展示；
- 下载按钮可用；
- 非联网测试全通过，M3 gate 退出 0。
