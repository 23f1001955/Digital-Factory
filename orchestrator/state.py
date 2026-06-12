import json
import os
from .models import JobState, AgentResult

def load_job_state(filepath: str, default_slug: str) -> JobState:
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            data = json.load(f)
            return JobState(**data)
    return JobState(slug=default_slug)

def save_job_state(state: JobState, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(state.model_dump(mode="json"), f, indent=2)
