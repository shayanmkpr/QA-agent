import tempfile
import os
from app.scenarios.parser import parse_scenarios
from app.scenarios.models import Scenario


SAMPLE_MD = """## 1. Landing — Navigation — Entry Points

### Scenario 1: Navigation & CTAs

- Click header buttons (Login / Signup / Pricing)
- Click footer links
- Click all CTAs

**Expected:**
- All links work correctly
- No broken links

### Scenario 2: Banner Behavior

- Open landing (logged-out)
- Login and revisit
- Click banner CTAs

**Expected:**
- Banner changes based on user state
- CTA redirects correctly

---

## 2. Authentication Flow

### Scenario 3: Signup & Login

- Signup with email + OTP (valid / invalid / expired)
- Login with valid / invalid credentials

**Expected:**
- Valid flows succeed
- Invalid inputs show error

### Scenario 4: Forgot Password

- Request reset (valid / invalid email)
- Enter valid / invalid / expired OTP

**Expected:**
- Reset works only with valid data
- Old password no longer works

### Scenario 5: Notifications

- Complete Signup / Login / Reset

**Expected:**
- Events logged in Slack
- Welcome email sent

---

## 3. Pricing — Plan — Access Control

### Scenario 6: Pricing Flow

- Click plan (logged-out / logged-in)
- Click Upgrade / Downgrade / Buy credits

**Expected:**
- Correct auth / checkout flow

## 11. User Types & Credit Behavior

### Scenario 22: Free User

- Generate image
- Download image

**Expected:**
- Watermark visible
"""


def test_parses_correct_number_of_scenarios():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(SAMPLE_MD)
        tmp_path = f.name

    try:
        scenarios = parse_scenarios(tmp_path)
        assert len(scenarios) == 7
    finally:
        os.unlink(tmp_path)


def test_scenario_fields():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(SAMPLE_MD)
        tmp_path = f.name

    try:
        scenarios = parse_scenarios(tmp_path)

        s1 = scenarios[0]
        assert s1.id == 1
        assert s1.title == "Navigation & CTAs"
        assert s1.section == "Landing — Navigation — Entry Points"
        assert s1.section_number == 1
        assert len(s1.steps) == 3
        assert len(s1.expected) == 2
        assert "Click header buttons" in s1.steps[0]
        assert "All links work correctly" in s1.expected[0]
    finally:
        os.unlink(tmp_path)


def test_auth_flags():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(SAMPLE_MD)
        tmp_path = f.name

    try:
        scenarios = parse_scenarios(tmp_path)

        # Scenarios 1-2: no auth
        assert not scenarios[0].requires_auth
        assert not scenarios[0].is_auth_scenario
        assert not scenarios[1].requires_auth
        assert not scenarios[1].is_auth_scenario

        # Scenarios 3-5: auth scenarios
        assert scenarios[2].is_auth_scenario
        assert not scenarios[2].requires_auth
        assert scenarios[3].is_auth_scenario
        assert scenarios[4].is_auth_scenario

        # Scenario 6+: requires auth
        assert scenarios[5].requires_auth
        assert not scenarios[5].is_auth_scenario
        assert scenarios[5].id == 6
    finally:
        os.unlink(tmp_path)


def test_empty_expected_handled():
    """Scenario with no Expected section should have empty expected list."""
    md = """## 1. Test

### Scenario 1: Test

- Step one
- Step two
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(md)
        tmp_path = f.name

    try:
        scenarios = parse_scenarios(tmp_path)
        assert len(scenarios) == 1
        assert len(scenarios[0].steps) == 2
        assert len(scenarios[0].expected) == 0
    finally:
        os.unlink(tmp_path)


def test_parse_real_scenarios_file():
    """Integration test: parse the actual scenarios.md file."""
    scenarios = parse_scenarios("docs/scenarios.md")
    assert len(scenarios) == 26

    titles = {s.id: s.title for s in scenarios}
    assert titles[1] == "Navigation & CTAs"
    assert titles[10] == "VS Variations"
    assert titles[26] == "Credit Logic"

    for s in scenarios:
        assert isinstance(s, Scenario)
        assert s.id > 0
        assert s.title
        assert s.section
