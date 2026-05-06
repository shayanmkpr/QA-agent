from app.scenarios.models import Scenario
from prompts.templates import scenario_execution


def build_scenario_prompt(scenario: Scenario, credentials: dict, base_url: str) -> str:
    return scenario_execution(
        scenario_id=scenario.id,
        scenario_title=scenario.title,
        section=scenario.section,
        base_url=base_url,
        steps=scenario.steps,
        expected=scenario.expected,
        credentials=credentials,
        requires_auth=scenario.requires_auth,
        is_auth_scenario=scenario.is_auth_scenario,
    )
