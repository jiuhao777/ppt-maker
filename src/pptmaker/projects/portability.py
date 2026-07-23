import json

from pydantic import ValidationError

from pptmaker.projects.models import Project, ProjectCreate, ProjectExport
from pptmaker.projects.repository import ProjectRepository


class InvalidProjectImport(ValueError):
    pass


MAX_PROJECT_BYTES = 5 * 1024 * 1024


def export_project(project: Project) -> bytes:
    exported = ProjectExport(
        project_id=project.id,
        name=project.name,
        business_state=project.business_state,
        execution_state=project.execution_state,
        last_provider_preset=project.last_provider_preset,
        created_at=project.created_at,
        updated_at=project.updated_at,
        web_policy=project.web_policy,
    )
    return exported.model_dump_json().encode("utf-8")


def _check_limits(value) -> None:
    stack = [(value, 1)]
    keys = 0
    while stack:
        current, depth = stack.pop()
        if depth > 20:
            raise InvalidProjectImport("JSON nesting exceeds 20 levels")
        if isinstance(current, dict):
            keys += len(current)
            if keys > 10_000:
                raise InvalidProjectImport("JSON contains too many keys")
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
        elif isinstance(current, str) and len(current) > 1024 * 1024:
            raise InvalidProjectImport("JSON string exceeds 1 MiB")


def import_project(data: bytes, repository: ProjectRepository) -> Project:
    if len(data) > MAX_PROJECT_BYTES:
        raise InvalidProjectImport("JSON file exceeds 5 MiB")
    try:
        decoded = json.loads(data)
        _check_limits(decoded)
        exported = ProjectExport.model_validate(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise InvalidProjectImport("Invalid project JSON") from exc
    return repository.create(
        ProjectCreate(
            name=exported.name,
            business_state=exported.business_state,
            execution_state=(
                "FAILED_RECOVERABLE"
                if exported.execution_state in {"RUNNING", "CANCELLING"}
                else exported.execution_state
            ),
            last_provider_preset=exported.last_provider_preset,
            web_policy=exported.web_policy,
        ),
        created_at=exported.created_at,
        updated_at=exported.updated_at,
    )
