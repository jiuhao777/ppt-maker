from pptmaker.projects import ProjectRepository


def reconcile_interrupted_projects(repository: ProjectRepository) -> int:
    return repository.mark_running_recoverable()
