import re
import unicodedata
from typing import Tuple

# Normalizează: litere mici + fără diacritice (pentru a prinde „tâmpit/tampit”, „prost/ș.a.”)
def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text

# Stems (română + câteva englezisme uzuale). Se caută ca "cuvânt" cu sufixe flexionare.
# Exemplu: r"\bprost\w*\b" va prinde "prost", "prostu", "proasta", "prostule".
_BAD_STEMS = [
    "prost", "idiot", "tampit", "bou", "dobitoc", "porc", "fraier",
    "nesimtit",  # atenție: ofensiv — exact ce vrem să blocăm
    # Eng:
    "stupid", "dumb", "idiot", "moron",
]

# Expresii vulgare (detectate ca substrings normale, după normalizare)
_BAD_PHRASES = [
    "du-te drac", "du te drac",
]

_PATTERNS = [re.compile(rf"\b{stem}\w*\b") for stem in _BAD_STEMS]

def check_inappropriate(text: str) -> Tuple[bool, str]:
    """
    Returnează (is_bad, match_str). Marcăm mesajul ca nepotrivit dacă găsim un stem/expresie.
    """
    if not text:
        return False, ""
    norm = _normalize(text)

    # expresii
    for ph in _BAD_PHRASES:
        if ph in norm:
            return True, ph

    # stems
    for pat in _PATTERNS:
        m = pat.search(norm)
        if m:
            return True, m.group(0)

    return False, ""
