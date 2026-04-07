import sys
import io
import re

# Set stdout encoding to utf-8 if it's not
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pytest

@pytest.mark.parametrize("text, is_death, victim, killer", [
    ("Tribemember TPR - Lvl 140 was :knife:!", True, "TPR", None),
    ("Tribemember TPR - Lvl 140 was :knife:", True, "TPR", None),
    ("Tribemember TPR - Lvl 140 was 🔪", True, "TPR", None),
    ("Tribemember TPR - Lvl 140 ha muerto 🔪", True, "TPR", None),
    ("Tribemember TPR - Lvl 140 was 🔪 by Alpha T-Rex - Lvl 12", True, "TPR", "Alpha T-Rex"),
    ("Just a random chat message with :knife:", False, None, None),
])
def test_death_detection(text, is_death, victim, killer):
    t_clean = (
        text.replace(":knife:", "🔪")
        .replace("was 🔪 by", "fue 🔪 por")
        .replace("was 🔪", "ha muerto 🔪")
    )
    
    player_death_match = re.search(
        r"Tribemember (.*?) - Lvl.*?fue 🔪 por (.*?) - Lvl",
        t_clean,
        re.IGNORECASE,
    )

    generic_death_match = re.search(
        r"Tribemember (.*?) - Lvl.*?(?:ha muerto 🔪|was 🔪)",
        t_clean,
        re.IGNORECASE,
    )

    if not is_death:
        assert not player_death_match
        assert not generic_death_match
        return

    # Check if detection matched
    assert player_death_match or generic_death_match
    
    if killer:
        assert player_death_match is not None
        assert player_death_match.group(1).strip() == victim
        assert player_death_match.group(2).strip() == killer
    else:
        assert generic_death_match is not None
        assert generic_death_match.group(1).strip() == victim
