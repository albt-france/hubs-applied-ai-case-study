"""Demo mode for CX Pulse: a keyword classifier in Portuguese (no AI, no API key).

It is the honest baseline: what a team would build in an afternoon without a model.
The keyword lists were written from general Portuguese e-commerce vocabulary, not tuned on
the test set. The evaluation compares it with the model.
"""
from __future__ import annotations

import re
import unicodedata


def _norm(text: str) -> str:
    """Lowercase and remove accents so 'não' and 'nao' match the same rule."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


# Ordered by precedence: the first matching theme wins.
RULES: list[tuple[str, list[str]]] = [
    ("not_received", [r"nao (recebi|chegou|foi entregue|recebemos)", r"ainda nao", r"nunca chegou",
                      r"aguardando (o produto|a entrega|meu|minha)", r"ate (agora|hoje|hj) nao", r"nao entregue",
                      r"cade (o|meu) produto"]),
    ("wrong_or_incomplete", [r"errad", r"diferente do (que|qual)", r"outro produto", r"veio outr",
                             r"apenas (um|uma)\b", r"somente (um|uma)\b", r"falt(ou|ando|a um)", r"incomplet",
                             r"nao veio", r"so veio", r"nao foi o comprado"]),
    ("damaged_defective", [r"quebrad", r"defeito", r"danificad", r"nao (funciona|liga|desliga)",
                           r"parou de funcionar", r"rachad", r"amassad", r"arranh", r"riscad", r"estragad",
                           r"descascad", r"usado"]),
    ("seller_service", [r"cancel", r"estorn", r"reembols", r"devolu", r"devolver", r"dinheiro de volta",
                        r"nao respond", r"sem resposta", r"atendimento", r"nota fiscal", r"\btroca"]),
    ("delivery_late", [r"atras", r"demor", r"fora do prazo", r"passou do prazo", r"prazo (de entrega )?muito",
                       r"venceu", r"lent[oa]", r"muito tempo"]),
    ("quality_mismatch", [r"(baixa|ma|pessima|qualidade) qualidade|qualidade (ruim|baixa|pessima)",
                          r"nao corresponde", r"diferente da (foto|imagem)", r"cor diferente", r"nao e (essa|a mesma) cor",
                          r"fragil", r"frac[oa]", r"desalinhad", r"nao gostei"]),
    ("other", [r"correios", r"retirar", r"frete", r"ruim", r"pessim", r"nao recomendo", r"nao cumpriu",
               r"decepcion", r"insatisf"]),
]

HIGH_BY_DEFAULT = {"not_received", "wrong_or_incomplete", "damaged_defective", "seller_service"}


def classify(text: str, score: int) -> tuple[str, str]:
    """Return (theme, severity) for one review."""
    t = _norm(text)
    theme = "praise"
    for name, patterns in RULES:
        if any(re.search(p, t) for p in patterns):
            theme = name
            break
    if theme == "praise":
        return theme, "none"
    if score >= 4:  # complaint inside a happy review
        return theme, "low"
    if theme in HIGH_BY_DEFAULT or re.search(r"cancel", t):
        return theme, "high"
    return theme, "medium"
