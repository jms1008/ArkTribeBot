import sys
import io
import re

# Set stdout encoding to utf-8 if it's not
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_death_detection(text):
    # Simulating the bot's cleaning logic
    t_clean = (
        text.replace(":knife:", "🔪")
        .replace("was 🔪 by", "fue 🔪 por")
        .replace("was 🔪", "ha muerto 🔪")
    )
    
    # 1. Caso: Muerte confirmada con asesino
    player_death_match = re.search(
        r"Tribemember (.*?) - Lvl.*?fue 🔪 por (.*?) - Lvl",
        t_clean,
        re.IGNORECASE,
    )

    # 2. Caso: Muerte genérica
    generic_death_match = re.search(
        r"Tribemember (.*?) - Lvl.*?(?:ha muerto 🔪|was 🔪)",
        t_clean,
        re.IGNORECASE,
    )

    print(f"Original: {text}")
    print(f"Cleaned:  {t_clean}")
    
    if player_death_match:
        print(f"MATCH: Player Death | Victim: '{player_death_match.group(1)}' | Killer: '{player_death_match.group(2)}'")
    elif generic_death_match:
        print(f"MATCH: Generic Death | Victim: '{generic_death_match.group(1)}'")
    else:
        print("NO MATCH")
    print("-" * 20)

# Test cases
test_death_detection("Tribemember TPR - Lvl 140 was :knife:!")
test_death_detection("Tribemember TPR - Lvl 140 was :knife:")
test_death_detection("Tribemember TPR - Lvl 140 was 🔪")
test_death_detection("Tribemember TPR - Lvl 140 ha muerto 🔪")
test_death_detection("Tribemember TPR - Lvl 140 was 🔪 by Alpha T-Rex - Lvl 12")
