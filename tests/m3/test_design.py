import math

import pytest

from pptmaker.m3.models import DesignPlan, ColorPalette, FontSet
from pptmaker.m2.models import RequirementBrief
from pptmaker.m3.design import PRESETS, plan_design


def _brief(**kwargs) -> RequirementBrief:
    return RequirementBrief(project_id="p1", **kwargs)


class TestPresets:
    def test_all_five_presets_defined(self):
        assert set(PRESETS) == {"business", "academic", "creative", "minimal", "tech"}

    def test_business_preset_has_valid_contrast(self):
        plan = PRESETS["business"]
        ratio = _contrast(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5

    def test_academic_preset_has_valid_contrast(self):
        plan = PRESETS["academic"]
        ratio = _contrast(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5

    def test_creative_preset_has_valid_contrast(self):
        plan = PRESETS["creative"]
        ratio = _contrast(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5

    def test_minimal_preset_has_valid_contrast(self):
        plan = PRESETS["minimal"]
        ratio = _contrast(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5

    def test_tech_preset_has_valid_contrast(self):
        plan = PRESETS["tech"]
        ratio = _contrast(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5

    def test_preset_fonts_are_readable(self):
        for name, plan in PRESETS.items():
            assert plan.fonts.title_size >= 24, f"{name} title too small"
            assert plan.fonts.body_size >= 14, f"{name} body too small"


class TestPresetMode:
    def test_returns_preset_without_calling_llm(self):
        plan = plan_design(_brief(), "business", None, "")
        assert plan.preset == "business"
        assert plan.palette.primary == PRESETS["business"].palette.primary

    def test_unknown_preset_falls_back_to_custom(self):
        class FakeModel:
            def generate(self, schema, system, prompt, api_key):
                return DesignPlan(
                    project_id="p1",
                    preset="custom",
                    palette=ColorPalette(
                        primary="#333333", secondary="#666666",
                        accent="#FF6600", background="#FFFFFF",
                        text_primary="#111111", text_secondary="#888888",
                    ),
                    fonts=FontSet(),
                    style_notes="custom fallback",
                )

        plan = plan_design(_brief(), "nonexistent", FakeModel(), "KEY")
        assert plan.preset == "custom"


class TestAutoMode:
    def test_auto_calls_llm_and_returns_custom(self):
        class FakeModel:
            def generate(self, schema, system, prompt, api_key):
                return DesignPlan(
                    project_id="p1",
                    preset="custom",
                    palette=ColorPalette(
                        primary="#2C3E50", secondary="#3498DB",
                        accent="#E74C3C", background="#FFFFFF",
                        text_primary="#2C3E50", text_secondary="#7F8C8D",
                    ),
                    fonts=FontSet(),
                    style_notes="auto generated",
                )

        plan = plan_design(_brief(), "auto", FakeModel(), "KEY")
        assert plan.preset == "custom"
        assert plan.palette.primary == "#2C3E50"

    def test_auto_corrects_low_contrast(self):
        class FakeModel:
            def generate(self, schema, system, prompt, api_key):
                return DesignPlan(
                    project_id="p1",
                    preset="custom",
                    palette=ColorPalette(
                        primary="#AAAAAA", secondary="#BBBBBB",
                        accent="#CCCCCC", background="#AAAAAA",  # identical = 1:1 contrast
                        text_primary="#AAAAAA", text_secondary="#BBBBBB",
                    ),
                    fonts=FontSet(),
                    style_notes="bad contrast",
                )

        plan = plan_design(_brief(), "auto", FakeModel(), "KEY")
        ratio = _contrast(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5, f"auto-corrected contrast {ratio} still too low"


def _contrast(hex_a: str, hex_b: str) -> float:
    def _luminance(hex_color: str) -> float:
        rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    l1, l2 = _luminance(hex_a), _luminance(hex_b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
