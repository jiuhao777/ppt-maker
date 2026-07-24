import math as _math

from pptmaker.m2.models import RequirementBrief
from pptmaker.m3.models import ColorPalette, DesignPlan, FontSet
from pptmaker.providers.structured import StructuredModel


# ── WCAG Contrast Ratio ────────────────────────────────────────

def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        for c in rgb
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    l1, l2 = _luminance(hex_a), _luminance(hex_b)
    lighter, darker = (l1, l2) if l1 > l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def _darken(hex_color: str, amount: int) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"#{max(0, r - amount):02X}{max(0, g - amount):02X}{max(0, b - amount):02X}"


def _lighten(hex_color: str, amount: int) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"#{min(255, r + amount):02X}{min(255, g + amount):02X}{min(255, b + amount):02X}"


def _correct_contrast(palette: ColorPalette) -> ColorPalette:
    ratio = contrast_ratio(palette.primary, palette.background)
    if ratio >= 4.5:
        return palette

    bg_luminance = _luminance(palette.background)

    # Try adjusting primary first
    for shift in (40, 80, 120):
        if bg_luminance > 0.5:
            primary = _darken(palette.primary, shift)
        else:
            primary = _lighten(palette.primary, shift)
        if contrast_ratio(primary, palette.background) >= 4.5:
            return palette.model_copy(update={"primary": primary})

    # Primary alone not enough — push background towards opposite extreme
    if bg_luminance > 0.5:
        return palette.model_copy(
            update={"primary": "#000000", "background": "#FFFFFF"}
        )
    return palette.model_copy(
        update={"primary": "#FFFFFF", "background": "#1A1A1A"}
    )


# ── Presets ─────────────────────────────────────────────────────

PRESETS: dict[str, DesignPlan] = {
    "business": DesignPlan(
        project_id="",
        preset="business",
        palette=ColorPalette(
            primary="#1F4E79",
            secondary="#5B9BD5",
            accent="#C59B27",
            background="#FFFFFF",
            text_primary="#1A1A1A",
            text_secondary="#666666",
        ),
        fonts=FontSet(),
        style_notes="商务专业：深蓝主色搭配金色强调，适合正式汇报与商业路演",
    ),
    "academic": DesignPlan(
        project_id="",
        preset="academic",
        palette=ColorPalette(
            primary="#1A365D",
            secondary="#2B6CB0",
            accent="#3182CE",
            background="#F7FAFC",
            text_primary="#1A202C",
            text_secondary="#4A5568",
        ),
        fonts=FontSet(),
        style_notes="学术严谨：深藏青搭配浅灰背景，适合答辩与数据报告",
    ),
    "creative": DesignPlan(
        project_id="",
        preset="creative",
        palette=ColorPalette(
            primary="#BF360C",
            secondary="#F57C00",
            accent="#FFC107",
            background="#FFFFFF",
            text_primary="#212121",
            text_secondary="#616161",
        ),
        fonts=FontSet(title_zh="微软雅黑", body_zh="微软雅黑",
                       title_en="Arial", body_en="Arial",
                       title_size=32, subtitle_size=22, body_size=16),
        style_notes="创意活力：暖橙搭配暖白背景，适合活动宣讲与创意提案",
    ),
    "minimal": DesignPlan(
        project_id="",
        preset="minimal",
        palette=ColorPalette(
            primary="#1A1A1A",
            secondary="#4A4A4A",
            accent="#757575",
            background="#FFFFFF",
            text_primary="#1A1A1A",
            text_secondary="#666666",
        ),
        fonts=FontSet(),
        style_notes="极简干净：黑白灰极简配色，适合课件与内部讨论",
    ),
    "tech": DesignPlan(
        project_id="",
        preset="tech",
        palette=ColorPalette(
            primary="#4A148C",
            secondary="#7B1FA2",
            accent="#00BCD4",
            background="#FAFAFE",
            text_primary="#1A1A2E",
            text_secondary="#555570",
        ),
        fonts=FontSet(),
        style_notes="科技未来：深紫配青色强调，适合技术分享与产品发布",
    ),
}


# ── Planner ──────────────────────────────────────────────────────

def plan_design(
    brief: RequirementBrief,
    style_preset: str,
    model: StructuredModel | None,
    api_key: str,
) -> DesignPlan:
    if style_preset in PRESETS:
        return PRESETS[style_preset].model_copy(
            update={"project_id": brief.project_id}
        )

    result = model.generate(
        DesignPlan,
        (
            "根据任务类型、受众和风格偏好，选择配色方案和字体。"
            "配色必须满足 WCAG AA 对比度（主色与背景 ≥ 4.5:1）。"
            "学术答辩偏保守，路演偏醒目，课件偏友好。"
            "标题 ≥ 24pt，正文 ≥ 14pt。"
            "preset 字段填 \"custom\"。"
        ),
        brief.model_dump_json(),
        api_key,
    )
    corrected = result.model_copy(
        update={
            "palette": _correct_contrast(result.palette),
            "project_id": brief.project_id,
        }
    )
    return corrected
