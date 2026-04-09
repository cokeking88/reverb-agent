"""Skills management."""

import json
import time
import uuid
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel


class Step(BaseModel):
    """Skill step."""
    action: str
    params: dict = {}


class Skill(BaseModel):
    """Skill definition."""
    id: str
    name: str
    description: str
    trigger: str
    steps: List[Step]
    created_at: float = 0
    usage_count: int = 0
    version: int = 1


class SkillManager:
    """Skill manager."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> List[Skill]:
        """List all skills."""
        skills = []
        for f in self.skills_dir.glob("*.json"):
            try:
                with open(f) as fp:
                    skills.append(Skill(**json.load(fp)))
            except:
                pass
        return skills

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        path = self.skills_dir / f"{skill_id}.json"
        if path.exists():
            try:
                with open(path) as fp:
                    return Skill(**json.load(fp))
            except:
                pass
        return None

    def add_skill(self, skill: Skill) -> None:
        """Save a skill."""
        path = self.skills_dir / f"{skill.id}.json"
        with open(path, "w") as fp:
            json.dump(skill.model_dump(), fp, indent=2)

    def create_skill(self, name: str, description: str, trigger: str, steps: List[dict]) -> Skill:
        """Create a new skill."""
        skill = Skill(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            trigger=trigger,
            steps=[Step(**s) for s in steps],
            created_at=time.time()
        )
        self.add_skill(skill)
        return skill

    async def execute_skill(self, skill_id: str) -> dict:
        """Execute a skill."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": f"Skill {skill_id} not found"}

        skill.usage_count += 1
        self.add_skill(skill)

        return {"status": "executed", "skill": skill.name, "steps": len(skill.steps)}