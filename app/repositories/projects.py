"""Database operations for Project records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.projects import ProjectInput


class ProjectRepository:
    """Read and write Project rows with a SQLAlchemy Session."""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[Project]:
        statement = select(Project).order_by(Project.name)
        return list(self.session.scalars(statement))

    def get_by_id(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)


    def get_by_name(self, name: str) -> Project | None:
        statement = select(Project).where(Project.name == name)
        return self.session.scalars(statement).first()


    def create(self, data: ProjectInput) -> Project:
        project = Project(**data.model_dump())
        self.session.add(project)
        # Flush sends INSERT and makes the generated ID available.
        self.session.flush()
        return project

    def replace(self, project: Project, data: ProjectInput) -> Project:
        project.name = data.name
        project.description = data.description
        self.session.flush()
        return project

    def delete(self, project: Project) -> None:
        self.session.delete(project)
