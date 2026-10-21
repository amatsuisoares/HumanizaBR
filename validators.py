"""Verificações determinísticas de fidelidade entre o texto original e o reescrito.

Ideia central: alguns elementos de um texto (números, datas, citações, siglas,
trechos entre aspas, URLs...) podem ser extraídos com expressões regulares e
comparados diretamente. Se algo some ou aparece do nada, avisamos o usuário.

Essas verificações são *heurísticas*: detectam muitos problemas comuns, mas não
garantem que o significado foi preservado (isso exige leitura humana). Elas
também podem gerar falsos positivos — por exemplo, se o modelo escrever "dez"
no lugar de "10". Por isso a interface fala em "possíveis" alterações.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from style import new_cliches

CRITICAL = "critico"
WARNING = "aviso"

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

# Letras maiúsculas/minúsculas incluindo acentuadas do português.
_UP = "A-ZÀ-ÖØ-Þ"
_LO = "a-zß-öø-ÿ"
_WORD_RE = re.compile(rf"[{_UP}{_LO}0-9][{_UP}{_LO}0-9_\-]*")

_DATE_NUMERIC = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b")
_DATE_TEXT = re.compile(
    rf"\b(\d{{1,2}})º?\s+de\s+({_MONTH_RE})(?:\s+de\s+(\d{{4}}))?\b", re.IGNORECASE
)
_DATE_MONTH_YEAR = re.compile(rf"\b({_MONTH_RE})\s+de\s+(\d{{4}})\b", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+(?:,\d+)?$")

_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+|[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)
# (SILVA, 2020)  (Silva; Souza, 2019, p. 12)  (OMS, 2021a)
_CITE_PAREN = re.compile(rf"\([^()]*[{_UP}][^()]*?,?\s*\d{{4}}[a-z]?(?:[^()]*)\)")
# Silva (2020)  Silva et al. (2019, p. 3)
_CITE_NARRATIVE = re.compile(
    rf"\b[{_UP}][{_LO}{_UP}]+(?:\s+et\s+al\.)?\s*\(\d{{4}}[a-z]?(?:,\s*p\.\s*\d+(?:-\d+)?)?\)"
)
# [1]  [2, 3]  [4-6]
_CITE_NUMERIC = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
_QUOTE = re.compile(r"[\"“]([^\"“”]{3,}?)[\"”]")

NEGATIONS = {"não", "nunca", "jamais", "nem", "nenhum", "nenhuma", "nada", "sem"}
HEDGES = {
    "pode", "podem", "poderia", "poderiam", "possivelmente", "talvez", "provavelmente",
    "provável", "possível", "sugere", "sugerem", "indica", "indicam", "aparentemente",
    "parece", "parecem", "estima", "estimam", "estimado", "estimada", "cerca", "aproximadamente",
    "hipótese", "eventualmente",
    # "se" e "caso" ficaram de fora de propósito: também são pronome/substantivo
    # ("trata-se", "o caso") e gerariam muitos falsos alarmes.
}
PT_STOPWORDS = {
    "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com", "não", "uma",
    "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi", "ao", "das",
    "à", "seu", "sua", "ou", "ser", "quando", "muito", "nos", "já", "está", "também", "pelo",
    "pela", "até", "isso", "ela", "entre", "era", "depois", "sem", "mesmo", "aos", "ter",
}
EN_STOPWORDS = {
    "the", "of", "and", "to", "in", "is", "that", "for", "it", "with", "as", "was", "on",
    "be", "at", "by", "this", "are", "from", "or", "an", "which", "but", "not", "have",
    "has", "were", "their", "they", "can", "will", "would", "been", "these", "its",
}
PREAMBLE = re.compile(
    r"^\s*(aqui está|aqui estão|claro[,!.]|segue|certamente|com certeza|texto reescrito|"
    r"versão (reescrita|revisada|corrigida)|reescrita:|resposta:)",
    re.IGNORECASE,
)


@dataclass
class Issue:
    severity: str          # CRITICAL ou WARNING
    category: str          # ex.: "números", "citações"
    message: str           # explicação para o usuário
    items: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def critical(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == CRITICAL]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == WARNING]

    @property
    def has_critical(self) -> bool:
        return bool(self.critical)

    def to_dict(self) -> dict:
        return {
            "issues": [vars(i) for i in self.issues],
            "stats": self.stats,
        }


# --------------------------------------------------------------------------
# Extração
# --------------------------------------------------------------------------

def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _year(y: str) -> str:
    return y if len(y) == 4 else ("20" + y if int(y) < 50 else "19" + y)


def extract_dates(text: str) -> tuple[set[str], str]:
    """Extrai datas normalizadas e devolve o texto sem elas.

    "15/03/2024" e "15 de março de 2024" viram ambos "15/03/2024", então trocar
    o formato da data não é tratado como erro. O texto devolvido tem as datas
    removidas, para que seus números não sejam contados duas vezes.
    """
    dates: set[str] = set()

    def numeric(m: re.Match) -> str:
        dates.add(f"{int(m[1]):02d}/{int(m[2]):02d}/{_year(m[3])}")
        return " "

    def textual(m: re.Match) -> str:
        month = MONTHS[m[2].lower()]
        dates.add(f"{int(m[1]):02d}/{month:02d}" + (f"/{m[3]}" if m[3] else ""))
        return " "

    def month_year(m: re.Match) -> str:
        dates.add(f"{MONTHS[m[1].lower()]:02d}/{m[2]}")
        return " "

    rest = _DATE_NUMERIC.sub(numeric, text)
    rest = _DATE_TEXT.sub(textual, rest)
    rest = _DATE_MONTH_YEAR.sub(month_year, rest)
    return dates, rest


def _canonical_number(n: str) -> str:
    n = n.rstrip(".,")
    if _THOUSANDS.match(n):  # 1.234.567,89 -> 1234567,89
        n = n.replace(".", "")
    return n


# Números por extenso, para que "6 horas" -> "seis horas" não seja um alarme falso.
# "um/uma" ficam de fora (quase sempre são artigos) e "mil" também ("2 mil" = 2000).
NUMBER_WORDS = {
    "dois": "2", "duas": "2", "três": "3", "quatro": "4", "cinco": "5", "seis": "6",
    "sete": "7", "oito": "8", "nove": "9", "dez": "10", "onze": "11", "doze": "12",
    "treze": "13", "catorze": "14", "quatorze": "14", "quinze": "15", "dezesseis": "16",
    "dezessete": "17", "dezoito": "18", "dezenove": "19", "vinte": "20", "trinta": "30",
    "quarenta": "40", "cinquenta": "50", "sessenta": "60", "setenta": "70",
    "oitenta": "80", "noventa": "90", "cem": "100",
}


def extract_numbers(text: str) -> set[str]:
    """Números (exceto os que fazem parte de datas), em forma canônica.

    Números por extenso simples ("seis") são convertidos para dígitos ("6").
    Compostos ("vinte e cinco") não são reconhecidos — limitação conhecida.
    """
    _, rest = extract_dates(text)
    rest = _URL.sub(" ", rest)
    numbers = {_canonical_number(n) for n in _NUMBER.findall(rest)}
    numbers.update(NUMBER_WORDS[w] for w in _words(rest.lower()) if w in NUMBER_WORDS)
    return numbers


def extract_urls(text: str) -> set[str]:
    return {u.rstrip(".,;:") for u in _URL.findall(text)}


def extract_citations(text: str) -> set[str]:
    found = set()
    for rx in (_CITE_PAREN, _CITE_NARRATIVE, _CITE_NUMERIC):
        found.update(_norm_space(c) for c in rx.findall(text))
    return found


def extract_quotes(text: str) -> set[str]:
    return {_norm_space(q) for q in _QUOTE.findall(text)}


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def extract_acronyms(text: str) -> set[str]:
    """Palavras com 2+ letras maiúsculas: IBGE, UFRJ, CNPq, COVID-19, SARS-CoV-2."""
    result = set()
    for w in _words(text):
        w = w.strip("-_")
        uppers = sum(1 for ch in w if ch.isupper())
        if uppers >= 2 and not w.isdigit():
            result.add(w)
    return result


def extract_technical_terms(text: str) -> set[str]:
    """Termos com "cara" de técnicos: código entre crases, camelCase,
    snake_case e palavras que misturam letras e dígitos (ex.: Python3, GPT-4)."""
    terms = {t for t in re.findall(r"`([^`]+)`", text)}
    for w in _words(text):
        w = w.strip("-_")
        if not w or w.isdigit():
            continue
        has_digit = any(c.isdigit() for c in w)
        has_alpha = any(c.isalpha() for c in w)
        camel = re.search(rf"[{_LO}][{_UP}]", w) is not None
        snake = "_" in w
        if (has_digit and has_alpha) or camel or snake:
            terms.add(w)
    return terms


_SENTENCE_START = re.compile(r"(?:^|[.!?:;]\s+|\n\s*|[\-•*]\s+)$")


def extract_proper_nouns(text: str) -> set[str]:
    """Palavras capitalizadas que NÃO estão em início de frase (heurística).

    Em português, palavras no meio da frase com inicial maiúscula costumam ser
    nomes próprios: Maria, Brasil, Petrobras, Universidade...
    """
    acronyms = extract_acronyms(text)
    result = set()
    for m in _WORD_RE.finditer(text):
        w = m.group().strip("-_")
        if len(w) < 2 or w in acronyms or not w[0].isupper():
            continue
        if not any(c.islower() for c in w):
            continue
        before = text[max(0, m.start() - 4): m.start()]
        if _SENTENCE_START.search(before) or m.start() == 0:
            continue
        result.add(w)
    return result


def _count_words(text: str, vocab: set[str]) -> int:
    return sum(1 for w in _words(text.lower()) if w in vocab)


def _contains_word(text: str, word: str, ignore_case: bool = False) -> bool:
    flags = re.IGNORECASE if ignore_case else 0
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text, flags) is not None


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def detect_language(text: str) -> str:
    """'pt', 'en' ou 'indefinido', contando palavras muito frequentes."""
    pt = _count_words(text, PT_STOPWORDS)
    en = _count_words(text, EN_STOPWORDS)
    if pt == en == 0:
        return "indefinido"
    return "pt" if pt >= en else "en"


def text_similarity(a: str, b: str) -> float:
    """Similaridade entre 0 e 1, caractere a caractere.

    Comparar por caracteres (e não por palavras) faz "aluno" -> "alunos" contar
    como uma mudança pequena, o que é justo para correções gramaticais.
    """
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


# --------------------------------------------------------------------------
# Validação
# --------------------------------------------------------------------------

def _compare_sets(
    report: ValidationReport,
    original: set[str],
    rewritten: set[str],
    category: str,
    missing_severity: str,
    added_severity: str | None,
) -> None:
    missing = sorted(original - rewritten)
    added = sorted(rewritten - original)
    if missing:
        report.issues.append(Issue(
            missing_severity, category,
            f"Possível perda de {category}: presentes no original, ausentes no resultado.",
            missing,
        ))
    if added and added_severity:
        report.issues.append(Issue(
            added_severity, category,
            f"Possível conteúdo inventado ({category}): aparecem no resultado, mas não no original.",
            added,
        ))


def validate(
    original: str,
    rewritten: str,
    mode: str = "natural",
    protected_terms: list[str] | None = None,
) -> ValidationReport:
    """Compara original e resultado e devolve um relatório de possíveis problemas."""
    report = ValidationReport()

    if not rewritten.strip():
        report.issues.append(Issue(CRITICAL, "resposta", "O resultado está vazio."))
        return report

    # 1. Elementos que devem ser preservados exatamente.
    _compare_sets(report, extract_numbers(original), extract_numbers(rewritten),
                  "números", CRITICAL, CRITICAL)
    _compare_sets(report, extract_dates(original)[0], extract_dates(rewritten)[0],
                  "datas", CRITICAL, CRITICAL)
    _compare_sets(report, extract_citations(original), extract_citations(rewritten),
                  "citações/referências", CRITICAL, CRITICAL)
    _compare_sets(report, extract_quotes(original), extract_quotes(rewritten),
                  "trechos entre aspas", CRITICAL, None)
    _compare_sets(report, extract_urls(original), extract_urls(rewritten),
                  "URLs/e-mails", CRITICAL, CRITICAL)
    _compare_sets(report, extract_acronyms(original), extract_acronyms(rewritten),
                  "siglas", WARNING, WARNING)
    _compare_sets(report, extract_technical_terms(original), extract_technical_terms(rewritten),
                  "termos técnicos", WARNING, None)

    # 2. Nomes próprios: o nome pode passar a abrir uma frase, então basta
    #    que apareça em qualquer posição do resultado.
    missing_names = sorted(n for n in extract_proper_nouns(original)
                           if not _contains_word(rewritten, n))
    if missing_names:
        report.issues.append(Issue(
            WARNING, "nomes próprios",
            "Possível perda de nomes próprios: presentes no original, ausentes no resultado.",
            missing_names,
        ))
    new_names = sorted(n for n in extract_proper_nouns(rewritten)
                       if not _contains_word(original, n, ignore_case=True)
                       and not _contains_word(_strip_accents(original), _strip_accents(n), True))
    if new_names:
        report.issues.append(Issue(
            WARNING, "nomes próprios",
            "Possíveis nomes novos no resultado (verifique se não foram inventados).",
            new_names,
        ))

    # 3. Termos que o usuário marcou como protegidos.
    for term in protected_terms or []:
        term = term.strip()
        if term and term.lower() in original.lower() and term.lower() not in rewritten.lower():
            report.issues.append(Issue(
                CRITICAL, "termos protegidos",
                "Um termo marcado como protegido não aparece no resultado.", [term],
            ))

    # 4. Negações e grau de certeza.
    neg_o, neg_r = _count_words(original, NEGATIONS), _count_words(rewritten, NEGATIONS)
    if neg_r < neg_o:
        report.issues.append(Issue(
            WARNING, "negações",
            f"O original tem {neg_o} negação(ões) (não, nunca, nem...) e o resultado tem {neg_r}. "
            "Verifique se o sentido de alguma frase foi invertido.",
        ))
    hedge_o, hedge_r = _count_words(original, HEDGES), _count_words(rewritten, HEDGES)
    if hedge_o and hedge_r < hedge_o:
        report.issues.append(Issue(
            WARNING, "grau de certeza",
            f"O original tem {hedge_o} marcador(es) de incerteza/condição (pode, talvez, se...) "
            f"e o resultado tem {hedge_r}. Verifique se alguma afirmação ficou mais categórica.",
        ))

    # 5. Idioma.
    lang_o, lang_r = detect_language(original), detect_language(rewritten)
    if lang_o == "pt" and lang_r == "en":
        report.issues.append(Issue(CRITICAL, "idioma", "O resultado parece estar em inglês."))

    # 6. Introduções e comentários indesejados.
    if PREAMBLE.search(rewritten) and not PREAMBLE.search(original):
        report.issues.append(Issue(
            WARNING, "formato",
            "O resultado parece começar com uma introdução ou comentário do modelo.",
        ))

    # 7. Clichês que o modelo acrescentou (os que já estavam no original não contam).
    added = new_cliches(original, rewritten)
    if added:
        report.issues.append(Issue(
            WARNING, "clichês",
            "O resultado introduziu expressões batidas que não estavam no original.",
            sorted(added),
        ))

    # 8. Tamanho e quantidade de alterações, conforme o modo.
    len_o, len_r = len(original.split()), len(rewritten.split())
    ratio = len_r / len_o if len_o else 0.0
    similarity = text_similarity(original, rewritten)
    report.stats = {"razao_tamanho": round(ratio, 3), "similaridade": round(similarity, 3)}

    if ratio > 2.5 and len_o >= 5:
        # Nas avaliações, reescritas legítimas ficaram abaixo de ~1,5x. Muito acima
        # disso, é provável que o modelo tenha obedecido a um pedido contido no
        # texto (ex.: "escreva um poema") ou inventado conteúdo.
        report.issues.append(Issue(
            CRITICAL, "conteúdo divergente",
            f"O resultado tem {ratio:.1f}x o tamanho do original. O modelo pode ter seguido "
            "uma instrução contida no texto ou acrescentado conteúdo inventado.",
        ))
    elif mode == "conciso":
        if ratio > 1.0:
            report.issues.append(Issue(WARNING, "tamanho",
                                       "No modo Conciso o resultado deveria ser mais curto que o original."))
        elif ratio < 0.35 and len_o >= 20:
            report.issues.append(Issue(WARNING, "tamanho",
                                       "O resultado ficou muito mais curto; verifique se houve perda de informação."))
    elif len_o >= 15:
        if ratio < 0.6:
            report.issues.append(Issue(WARNING, "tamanho",
                                       "O resultado ficou bem mais curto que o original; possível omissão de conteúdo."))
        elif ratio > 1.6:
            report.issues.append(Issue(WARNING, "tamanho",
                                       "O resultado ficou bem mais longo que o original; possível acréscimo de conteúdo."))

    if mode == "gramatica" and similarity < 0.8:
        report.issues.append(Issue(
            WARNING, "alterações excessivas",
            f"No modo Correção gramatical o texto deveria mudar pouco, mas a similaridade foi de "
            f"{similarity:.0%}. Verifique se houve reescrita além da correção.",
        ))

    return report
