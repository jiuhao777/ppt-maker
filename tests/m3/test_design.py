import pytest

from pptmaker.m3.models import DesignPlan, ColorPalette, FontSet
from pptmaker.m2.models import RequirementBrief
from pptmaker.m3.design import PRESETS, plan_design, contrast_ratio


def _brief(**kwargs) -> RequirementBrief:
    return RequirementBrief(project_id="p1", **kwargs)


class TestPresets:
    def test_all_five_presets_defined(self):
        assert set(PRESETS) == {"business", "academic", "creative", "minimal", "tech"}

    @pytest.mark.parametrize("name", ["business", "academic", "creative", "minimal", "tech"])
    def test_preset_contrast_meets_wcag(self, name):
        plan = PRESETS[name]
        assert contrast_ratio(plan.palette.primary, plan.palette.background) >= 4.5

    def test_preset_fonts_are_readable(self):
        for name, plan in PRESETS.items():
            assert plan.fonts.title_size >= 24, f"{name} title too small"
            assert plan.fonts.body_size >= 14, f"{name} body too small"


class TestPresetMode:
    def test_returns_preset_without_calling_llm(self):
        plan = plan_design(_brief(), "business", None, "")
        assert plan.preset == "business"

    def test_unknown_preset_falls_back_to_custom(self):
        class Fake:
            def generate(self, *a, **kw):
                return DesignPlan(project_id="p1", preset="custom",
                    palette=ColorPalette(primary="#333333", secondary="#666666", accent="#FF6600",
                        background="#FFFFFF", text_primary="#111111", text_secondary="#888888"),
                    fonts=FontSet(), style_notes="fallback")
        plan = plan_design(_brief(), "nonexistent", Fake(), "KEY")
        assert plan.preset == "custom"


class TestAutoMode:
    def test_auto_calls_llm(self):
        class Fake:
            def generate(self, *a, **kw):
                return DesignPlan(project_id="p1", preset="custom",
                    palette=ColorPalette(primary="#2C3E50", secondary="#3498DB", accent="#E74C3C",
                        background="#FFFFFF", text_primary="#2C3E50", text_secondary="#7F8C8D"),
                    fonts=FontSet(), style_notes="auto")
        plan = plan_design(_brief(), "auto", Fake(), "KEY")
        assert plan.preset == "custom"

    def test_auto_corrects_low_contrast(self):
        class Fake:
            def generate(self, *a, **kw):
                return DesignPlan(project_id="p1", preset="custom",
                    palette=ColorPalette(primary="#AAAAAA", secondary="#BBBBBB", accent="#CCCCCC",
                        background="#AAAAAA", text_primary="#AAAAAA", text_secondary="#BBBBBB"),
                    fonts=FontSet(), style_notes="bad")
        plan = plan_design(_brief(), "auto", Fake(), "KEY")
        assert contrast_ratio(plan.palette.primary, plan.palette.background) >= 4.5
