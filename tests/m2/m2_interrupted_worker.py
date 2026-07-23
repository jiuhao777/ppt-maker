import sys
import time
from pathlib import Path

from pptmaker.m2.models import RequirementBrief
from pptmaker.m2.repository import M2Repository
from pptmaker.projects import ProjectCreate, ProjectRepository, ProjectUpdate


path = Path(sys.argv[1])
projects = ProjectRepository(path)
project = projects.create(ProjectCreate(name="Interrupted M2"))
M2Repository(path).save_brief(RequirementBrief(project_id=project.id))
projects.update(
    project.id,
    ProjectUpdate(execution_state="RUNNING"),
    expected_version=project.version,
)
print(project.id, flush=True)
time.sleep(60)
