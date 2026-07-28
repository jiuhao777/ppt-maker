from streamlit.testing.v1 import AppTest

from pptmaker.m2.models import DeckOutline, OutlinePage, RequirementBrief
from pptmaker.m2.repository import M2Repository
from pptmaker.projects import ProjectCreate, ProjectRepository
from pptmaker.ui.m2_workspace import (
    apply_pending_version,
    outline_version_label,
    queue_version_selection,
    web_generation_block,
)
from pptmaker.m2.interview import RequirementExtraction
from pptmaker.research.contracts import FreshnessDecision
from pptmaker.research.repository import ResearchRepository
from pptmaker.research.service import FreshnessService


def test_m2_workspace_shows_task_and_requirement_context(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    project = ProjectRepository(tmp_path / "pptmaker.db").create(
        ProjectCreate(name="M2 Demo")
    )
    M2Repository(tmp_path / "pptmaker.db").save_brief(
        RequirementBrief(project_id=project.id)
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert any(item.value == "任务与材料" for item in app.subheader)
    assert any(item.value == "已确认信息" for item in app.subheader)
    assert any(item.label == "不知道/不确定" for item in app.button)


def test_outline_approval_names_exact_version(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    project = ProjectRepository(tmp_path / "pptmaker.db").create(
        ProjectCreate(name="Outline Demo")
    )
    M2Repository(tmp_path / "pptmaker.db").create_outline(
        DeckOutline(
            project_id=project.id,
            version=1,
            status="DRAFT",
            narrative="Story",
            target_slides=1,
            pages=[
                OutlinePage(
                    order=1,
                    section="Intro",
                    title="Opening",
                    objective="Frame the topic",
                )
            ],
        )
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert any(item.label == "批准大纲 v1" for item in app.button)
    assert any(item.label == "新增页面" for item in app.button)
    assert any(item.label == "分析影响范围" for item in app.button)


def test_pending_version_becomes_selected_before_widget_creation():
    state = {}
    queue_version_selection(state, "p1", 2)

    apply_pending_version(state, "p1")

    assert state["m2_outline_version_p1"] == 2
    assert "m2_pending_version_p1" not in state


def test_version_label_includes_status_and_creation_method():
    outline = DeckOutline(
        project_id="p1",
        version=2,
        status="DRAFT",
        narrative="Story",
        target_slides=1,
        creation_method="MANUAL_EDIT",
        pages=[
            OutlinePage(
                order=1,
                section="Intro",
                title="Opening",
                objective="Frame",
            )
        ],
    )

    assert outline_version_label(outline) == "v2 · DRAFT · MANUAL_EDIT"


def test_always_without_verified_key_blocks_generation():
    project = ProjectCreate(name="Demo", web_policy="ALWAYS")

    block = web_generation_block(project, {})

    assert block.blocked
    assert block.banner == "当前项目要求联网，但尚未配置博查 API Key"
    assert block.button_label == "请先配置联网搜索"


def test_auto_without_key_does_not_block_generation():
    project = ProjectCreate(name="Demo", web_policy="AUTO")

    assert not web_generation_block(project, {}).blocked


def test_auto_without_key_offers_explicit_stale_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    projects = ProjectRepository(tmp_path / "pptmaker.db")
    project = projects.create(ProjectCreate(name="Fresh", web_policy="AUTO"))
    confirmed = {
        name: {"value": "已确认", "confidence": 1, "source": "user"}
        for name in (
            "purpose",
            "scenario",
            "target_slides",
            "audience",
            "priorities",
            "style",
        )
    }
    brief = RequirementBrief(project_id=project.id, **confirmed)
    M2Repository(projects.path).save_brief(brief)
    FreshnessService(
        object(), ResearchRepository(projects.path)
    ).plan(
        project.id,
        "AUTO",
        RequirementExtraction(
            brief=brief,
            ai_freshness=FreshnessDecision(
                requires_web=True,
                reason="内容会变化",
                freshness_level="HIGH",
            ),
        ),
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert any(item.label == "仍然继续生成" for item in app.button)
    assert any(item.label == "返回配置博查 Key" for item in app.button)
    assert not any(item.label == "生成结构大纲" for item in app.button)

    next(
        item for item in app.button if item.label == "仍然继续生成"
    ).click()
    app.run(timeout=10)

    assert any(item.label == "生成结构大纲" for item in app.button)
    assert (
        ResearchRepository(projects.path).get_latest_run(project.id).status
        == "SKIPPED_NO_KEY"
    )
