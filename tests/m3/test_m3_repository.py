import tempfile
from pathlib import Path

import pytest

from pptmaker.m3.models import ContentPlan, DesignPlan, SlideContent, ColorPalette, FontSet
from pptmaker.m3.repository import M3Repository
from pptmaker.m3.renderer import render_pptx, RenderError


class TestRepository:
    def test_content_round_trips(self):
        db = Path(tempfile.mktemp(suffix=".db"))
        repo = M3Repository(db)
        plan = ContentPlan(project_id="p1", outline_version=1,
            slides=[SlideContent(page_id="p1", title="T", body_paragraphs=["x"], bullet_points=[], source_references=[])])
        repo.save_content(plan)
        loaded = repo.get_content("p1", 1)
        assert loaded.slides[0].title == "T"

    def test_design_round_trips(self):
        db = Path(tempfile.mktemp(suffix=".db"))
        repo = M3Repository(db)
        plan = DesignPlan(project_id="p1", preset="business",
            palette=ColorPalette(primary="#1F4E79", secondary="#5B9BD5", accent="#C59B27",
                background="#FFFFFF", text_primary="#1A1A1A", text_secondary="#666666"),
            fonts=FontSet(), style_notes="test")
        repo.save_design(plan)
        loaded = repo.get_design("p1")
        assert loaded.preset == "business"

    def test_no_secrets_in_db(self):
        db = Path(tempfile.mktemp(suffix=".db"))
        repo = M3Repository(db)
        plan = ContentPlan(project_id="p1", outline_version=1,
            slides=[SlideContent(page_id="p1", title="T", body_paragraphs=[], bullet_points=[], source_references=[])])
        repo.save_content(plan)
        assert b"sk-" not in db.read_bytes()


class TestRenderer:
    def test_renderer_uses_m0_client(self, monkeypatch):
        from pptmaker.powerpoint.protocol import RenderResponse
        called = []

        def fake_render(req):
            called.append(req)
            return RenderResponse(status="success", slide_images=["/a/1.PNG"], elapsed_seconds=1.0)

        monkeypatch.setattr("pptmaker.m3.renderer.render_with_timeout", fake_render)
        paths = render_pptx(Path("fake.pptx"), Path(tempfile.mkdtemp()))
        assert len(called) == 1
        assert len(paths) == 1

    def test_renderer_raises_on_failure(self, monkeypatch):
        from pptmaker.powerpoint.protocol import RenderResponse

        monkeypatch.setattr("pptmaker.m3.renderer.render_with_timeout",
                            lambda req: RenderResponse(status="failed", elapsed_seconds=0, error="boom"))
        with pytest.raises(RenderError):
            render_pptx(Path("fake.pptx"), Path(tempfile.mkdtemp()))
