import tempfile
from pathlib import Path

import pytest

from pptmaker.m3.models import ContentPlan, DesignPlan, SlideContent, ColorPalette, FontSet
from pptmaker.m3.models import SlideSpec
from pptmaker.m3.artifacts import GenerationArtifact
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

    def test_specs_and_artifact_round_trip(self):
        db = Path(tempfile.mktemp(suffix=".db"))
        repo = M3Repository(db)
        spec = SlideSpec(
            page_id="p1",
            order=1,
            page_type="text",
            background_color="#FFFFFF",
        )
        repo.save_specs("p1", 2, [spec])
        artifact = GenerationArtifact(
            project_id="p1",
            blueprint_version=2,
            status="RUNNING",
        )
        repo.save_artifact(artifact)

        assert repo.get_specs("p1", 2)[0].page_id == "p1"
        assert repo.get_artifact("p1", 2).status == "RUNNING"

    def test_running_artifact_recovers_after_restart(self):
        db = Path(tempfile.mktemp(suffix=".db"))
        repo = M3Repository(db)
        repo.save_artifact(
            GenerationArtifact(
                project_id="p1",
                blueprint_version=1,
                status="RUNNING",
            )
        )

        assert repo.mark_running_recoverable() == 1
        recovered = repo.get_artifact("p1", 1)
        assert recovered.status == "FAILED_RECOVERABLE"
        assert recovered.safe_error_type == "interrupted"

    def test_recovery_is_scoped_to_current_project(self):
        db = Path(tempfile.mktemp(suffix=".db"))
        repo = M3Repository(db)
        for project_id in ("p1", "p2"):
            repo.save_artifact(
                GenerationArtifact(
                    project_id=project_id,
                    blueprint_version=1,
                    status="RUNNING",
                )
            )

        assert repo.mark_running_recoverable("p1") == 1
        assert repo.get_artifact("p1", 1).status == "FAILED_RECOVERABLE"
        assert repo.get_artifact("p2", 1).status == "RUNNING"


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
