import re
from app.scenarios.models import Scenario

_SECTION_RE = re.compile(r"^##\s+(\d+)\.\s+(.+)$")
_SCENARIO_RE = re.compile(r"^###\s+Scenario\s+(\d+):\s+(.+)$")
_BULLET_RE = re.compile(r"^-\s+(.+)$")


def parse_scenarios(filepath: str = "docs/scenarios.md") -> list[Scenario]:
    scenarios: list[Scenario] = []
    current_section_name = ""
    current_section_number = 0
    current_scenario: Scenario | None = None
    mode: str = "idle"  # idle, steps, expected

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()

        section_match = _SECTION_RE.match(stripped)
        if section_match:
            finalize_scenario(current_scenario, scenarios)
            current_scenario = None
            current_section_number = int(section_match.group(1))
            current_section_name = section_match.group(2).strip()
            mode = "idle"
            continue

        scenario_match = _SCENARIO_RE.match(stripped)
        if scenario_match:
            finalize_scenario(current_scenario, scenarios)
            current_scenario = Scenario(
                id=int(scenario_match.group(1)),
                title=scenario_match.group(2).strip(),
                section=current_section_name,
                section_number=current_section_number,
            )
            mode = "steps"
            continue

        if stripped.startswith("**Expected:**") or stripped.startswith("**Expected:**"):
            mode = "expected"
            continue

        if stripped.startswith("---"):
            continue

        bullet_match = _BULLET_RE.match(stripped)
        if bullet_match and current_scenario is not None:
            text = bullet_match.group(1).strip()
            if mode == "steps":
                current_scenario.steps.append(text)
            elif mode == "expected":
                current_scenario.expected.append(text)

    finalize_scenario(current_scenario, scenarios)

    _assign_auth_flags(scenarios)
    return scenarios


def finalize_scenario(scenario: Scenario | None, scenarios: list[Scenario]) -> None:
    if scenario is None:
        return
    if scenario.steps or scenario.expected:
        scenarios.append(scenario)


def _assign_auth_flags(scenarios: list[Scenario]) -> None:
    for s in scenarios:
        if s.id in (3, 4, 5):
            s.is_auth_scenario = True
        elif s.id >= 6:
            s.requires_auth = True
