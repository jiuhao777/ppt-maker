import sys
import time
from pathlib import Path

from pptmaker.projects import ProjectCreate, ProjectRepository, ProjectUpdate


repository = ProjectRepository(Path(sys.argv[1]))
project = repository.create(ProjectCreate(name="Interrupted"))
repository.update(
    project.id,
    ProjectUpdate(execution_state="RUNNING"),
    expected_version=project.version,
)
print(project.id, flush=True)
time.sleep(60)
