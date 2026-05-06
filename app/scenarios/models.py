from dataclasses import dataclass, field


@dataclass
class Scenario:
    """A single test scenario parsed from docs/scenarios.md."""
    id: int
    title: str
    section: str
    section_number: int
    steps: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)
    requires_auth: bool = False
    is_auth_scenario: bool = False


@dataclass
class ScenarioResult:
    """Outcome of executing a single scenario."""
    scenario_id: int
    section: str
    title: str
    status: str  # "PASS" | "FAIL" | "ERROR" | "SKIP"
    findings: str
    duration_seconds: float = 0.0
    steps_attempted: int = 0
    error_message: str = ""
