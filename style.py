"""Métricas de estilo do texto (determinísticas, sem modelo de linguagem).

Servem para medir se a reescrita ficou mais variada e menos "mecânica":

- **Variação das frases** ("burstiness"): coeficiente de variação do tamanho
  das frases (desvio padrão / média, em palavras). Frases todas do mesmo
  tamanho dão valor perto de 0; alternar frases curtas e longas aumenta o valor.
- **Variedade de vocabulário**: MATTR (Moving-Average Type-Token Ratio), a
  fração de palavras diferentes em janelas de 50 palavras. A janela evita que
  textos longos sejam penalizados só por serem longos.
  Observação: isto NÃO é a "perplexidade" no sentido técnico (que exige um
  modelo de linguagem para calcular probabilidades); é uma aproximação simples
  da ideia de "vocabulário menos previsível".
- **Voz passiva**: contagem heurística de "ser + particípio" ("foi realizado").
- **Clichês**: expressões batidas, muito comuns em textos gerados por IA.

Todas são heurísticas: ajudam a revisar, mas não substituem a leitura humana.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

# (rótulo exibido, expressão regular). O rótulo também é usado no prompt.
CLICHES: list[tuple[str, str]] = [
    ("essencial", r"essenciais|essencial"),
    ("fundamental", r"fundamentais|fundamental"),
    ("crucial", r"cruciais|crucial"),
    ("primordial", r"primordiais|primordial"),
    ("imprescindível", r"imprescindíveis|imprescindível"),
    ("de suma importância", r"de suma importância"),
    ("além disso", r"além disso"),
    ("ademais", r"ademais"),
    ("vale ressaltar", r"vale (?:ressaltar|destacar|salientar|lembrar|mencionar)"),
    ("é importante ressaltar", r"é (?:importante|válido|interessante) (?:ressaltar|destacar|notar|salientar|lembrar|mencionar)"),
    ("cabe ressaltar", r"cabe (?:ressaltar|destacar|salientar|mencionar)"),
    ("em suma", r"em suma"),
    ("em resumo", r"em resumo"),
    ("em síntese", r"em síntese"),
    ("em última análise", r"em última análise"),
    ("nesse sentido", r"ne(?:ss|st)e sentido"),
    ("nesse contexto", r"ne(?:ss|st)e contexto"),
    ("dessa forma", r"de(?:ss|st)a forma"),
    ("sendo assim", r"sendo assim"),
    ("no cenário atual", r"no cenário (?:atual|contemporâneo)"),
    ("no mundo atual", r"no mundo (?:atual|contemporâneo|moderno|de hoje)"),
    ("cada vez mais", r"cada vez mais"),
    ("desempenha um papel", r"desempenha(?:m)? (?:um )?papel"),
    ("não só... mas também", r"não (?:só|apenas|somente)\b[^.!?\n]{1,80}?\bmas também"),
    ("mergulhar", r"mergulh(?:ar|a|amos|aremos)"),
    ("jornada", r"jornada"),
    ("tapeçaria", r"tapeçaria"),
    ("potencializar", r"potencializ(?:ar|a|am|ando)"),
    ("alavancar", r"alavanc(?:ar|a|am|ando)"),
    ("robusto", r"robust[oa]s?"),
    ("abrangente", r"abrangentes?"),
    ("inegável", r"inegáve(?:l|is)|inegavelmente"),
]
_CLICHE_RES = [(label, re.compile(rf"\b(?:{rx})\b", re.IGNORECASE)) for label, rx in CLICHES]

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ]+)*")
# Fim de frase: . ! ? … seguidos de espaço, ou quebra de linha.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")

_PARTICIPLE = r"\w+(?:ad|id)[oa]s?|feit[oa]s?|dit[oa]s?|escrit[oa]s?|abert[oa]s?|post[oa]s?|vist[oa]s?|entregues?|aceit[oa]s?|eleit[oa]s?"
_PASSIVE = re.compile(
    rf"\b(?:é|são|foi|foram|será|serão|era|eram|seja|sejam|fosse|fossem|sido|ser)\s+(?:{_PARTICIPLE})\b",
    re.IGNORECASE,
)

MATTR_WINDOW = 50


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def split_sentences(text: str) -> list[str]:
    parts = (p.strip() for p in _SENTENCE_END.split(text))
    return [p for p in parts if words(p)]


def sentence_lengths(text: str) -> list[int]:
    return [len(words(s)) for s in split_sentences(text)]


def burstiness(text: str) -> float | None:
    """Coeficiente de variação do tamanho das frases. None se houver menos de 3 frases."""
    lengths = sentence_lengths(text)
    if len(lengths) < 3:
        return None
    return statistics.pstdev(lengths) / statistics.mean(lengths)


def lexical_diversity(text: str, window: int = MATTR_WINDOW) -> float | None:
    """MATTR: média da fração de palavras distintas em janelas deslizantes."""
    ws = words(text)
    if len(ws) < 10:
        return None
    if len(ws) <= window:
        return len(set(ws)) / len(ws)
    ratios = [len(set(ws[i:i + window])) / window for i in range(len(ws) - window + 1)]
    return statistics.mean(ratios)


def passive_count(text: str) -> int:
    return len(_PASSIVE.findall(text))


def find_cliches(text: str) -> dict[str, int]:
    """Clichês encontrados e quantas vezes aparecem."""
    found = {}
    for label, rx in _CLICHE_RES:
        n = len(rx.findall(text))
        if n:
            found[label] = n
    return found


def cliche_spans(text: str) -> list[tuple[int, int]]:
    """Posições (início, fim) dos clichês, sem sobreposição, em ordem."""
    spans = sorted(m.span() for _, rx in _CLICHE_RES for m in rx.finditer(text))
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return merged


def new_cliches(original: str, rewritten: str) -> dict[str, int]:
    """Clichês que aparecem MAIS vezes no resultado do que no original."""
    before = find_cliches(original)
    return {k: n - before.get(k, 0) for k, n in find_cliches(rewritten).items()
            if n > before.get(k, 0)}


@dataclass
class StyleReport:
    words: int
    sentences: int
    mean_sentence_len: float | None
    burstiness: float | None
    diversity: float | None
    passive: int
    cliches: dict[str, int] = field(default_factory=dict)
    lengths: list[int] = field(default_factory=list)

    @property
    def cliche_total(self) -> int:
        return sum(self.cliches.values())

    def to_dict(self) -> dict:
        r = lambda x: round(x, 3) if x is not None else None  # noqa: E731
        return {"palavras": self.words, "frases": self.sentences,
                "media_frase": r(self.mean_sentence_len), "variacao_frases": r(self.burstiness),
                "variedade_vocabulario": r(self.diversity), "voz_passiva": self.passive,
                "cliches": self.cliche_total}


def analyze(text: str) -> StyleReport:
    lengths = sentence_lengths(text)
    return StyleReport(
        words=len(words(text)),
        sentences=len(lengths),
        mean_sentence_len=statistics.mean(lengths) if lengths else None,
        burstiness=burstiness(text),
        diversity=lexical_diversity(text),
        passive=passive_count(text),
        cliches=find_cliches(text),
        lengths=lengths,
    )
