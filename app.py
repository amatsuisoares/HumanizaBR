"""Interface web do HumanizaBR (Streamlit).

Execute com:  streamlit run app.py

Esta camada só cuida da tela: toda a lógica de reescrita está em humanizer.py
e as verificações em validators.py. Para trocar o Streamlit por outra
interface no futuro, basta chamar as mesmas funções.

Como o Streamlit funciona: a cada clique, o script inteiro roda de novo de
cima para baixo. O que precisa sobreviver entre essas execuções fica em
`st.session_state` (os campos de texto com `key=` são guardados lá
automaticamente).
"""

from __future__ import annotations

import difflib
import html
import logging
import re

import streamlit as st

from config import Settings
from humanizer import HumanizerError, InvalidInputError, check_ollama, rewrite
from modes import MODES
from style import analyze, cliche_spans
from validators import CRITICAL, validate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = Settings.from_env()

st.set_page_config(page_title="HumanizaBR", page_icon="✍️", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1300px;}
      .hb-sub {color: #6b7280; margin-top: -0.6rem; margin-bottom: 1.2rem;}
      .hb-diff {line-height: 1.75; padding: 0.9rem 1rem; border-radius: 0.6rem;
                border: 1px solid rgba(128,128,128,0.25); white-space: pre-wrap;}
      .hb-diff del {background: rgba(239,68,68,0.18); color: inherit; text-decoration: line-through;}
      .hb-diff ins {background: rgba(34,197,94,0.22); color: inherit; text-decoration: none;}
      .hb-diff mark, .hb-box mark {background: rgba(245,158,11,0.3); color: inherit; border-radius: 3px;}
      .hb-box {padding: 0.9rem 1rem; border-radius: 0.6rem; white-space: pre-wrap;
               border: 1px solid rgba(128,128,128,0.25); min-height: 4rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ estado

DEFAULTS = {
    "input_text": "",
    "output_text": "",
    "mode": "natural",
    "last_original": "",   # texto que gerou o resultado atual (para comparar)
    "last_mode": None,
    "meta": None,
    "pending": False,      # pedido de reescrita aguardando execução
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


def request_rewrite() -> None:
    st.session_state.pending = True


def clear_all() -> None:
    for key in ("input_text", "output_text", "last_original"):
        st.session_state[key] = ""
    st.session_state.meta = st.session_state.last_mode = None


@st.cache_data(ttl=15, show_spinner=False)
def ollama_status(model: str, host: str) -> tuple[bool, str]:
    return check_ollama(settings)


def word_diff_html(a: str, b: str) -> str:
    """Diferenças palavra a palavra em HTML (texto escapado para evitar injeção de HTML)."""
    ta, tb = re.findall(r"\S+|\s+", a), re.findall(r"\S+|\s+", b)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        old, new = html.escape("".join(ta[i1:i2])), html.escape("".join(tb[j1:j2]))
        if op == "equal":
            out.append(old)
        if op in ("delete", "replace"):
            out.append(f"<del>{old}</del>")
        if op in ("insert", "replace"):
            out.append(f"<ins>{new}</ins>")
    return "".join(out)


def highlight_cliches(text: str) -> str:
    """Texto em HTML (escapado) com os clichês marcados."""
    out, pos = [], 0
    for start, end in cliche_spans(text):
        out += [html.escape(text[pos:start]), f"<mark>{html.escape(text[start:end])}</mark>"]
        pos = end
    out.append(html.escape(text[pos:]))
    return "".join(out)


def _fmt(value: float | None, pct: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}" if pct else f"{value:.2f}"


def _delta(new: float | None, old: float | None, pct: bool = False) -> str | None:
    if new is None or old is None:
        return None
    d = new - old
    return f"{d:+.0%}" if pct else f"{d:+.2f}"


# ------------------------------------------------------------------ barra lateral

with st.sidebar:
    st.subheader("Status")
    ok, status_msg = ollama_status(settings.model, settings.host)
    (st.success if ok else st.error)(status_msg)
    if st.button("Verificar novamente", use_container_width=True):
        ollama_status.clear()
        st.rerun()

    st.subheader("Termos protegidos")
    protected_raw = st.text_input(
        "Separe por vírgulas",
        key="protected_raw",
        placeholder="ex.: aprendizado de máquina, Lei 13.709",
        help="O modelo é instruído a manter esses termos, e o resultado é verificado.",
    )
    protected_terms = [t.strip() for t in protected_raw.split(",") if t.strip()]

    st.subheader("Configuração")
    st.caption(
        f"Modelo: `{settings.model}`  \n"
        f"Temperatura: {settings.temperature} · Máx. saída: {settings.max_output_tokens} tokens  \n"
        f"Limite de entrada: {settings.max_input_chars:,} caracteres".replace(",", ".")
    )
    st.caption(
        "🔒 Tudo roda nesta máquina. O texto é enviado apenas ao Ollama local "
        f"({settings.host}) e não é salvo em disco nem registrado em logs."
    )

# ------------------------------------------------------------------ cabeçalho e modo

st.title("✍️ HumanizaBR")
st.markdown('<p class="hb-sub">Reescrita de textos em português brasileiro, 100% local.</p>',
            unsafe_allow_html=True)

mode = st.segmented_control(
    "Modo de escrita",
    options=list(MODES),
    format_func=lambda k: MODES[k].label,
    key="mode",
)
if mode is None:  # o usuário clicou de novo no modo já selecionado
    mode = "natural"
st.caption(MODES[mode].description)

col_in, col_out = st.columns(2, gap="large")

# ------------------------------------------------------------------ entrada

with col_in:
    st.text_area(
        "Texto original",
        key="input_text",
        height=340,
        max_chars=settings.max_input_chars,
        placeholder="Cole ou digite aqui o texto que deseja reescrever...",
    )
    words = len(st.session_state.input_text.split())
    st.caption(f"{words} palavra(s)")
    b1, b2 = st.columns([3, 1])
    b1.button("✨ Reescrever", type="primary", use_container_width=True, on_click=request_rewrite)
    b2.button("Limpar", use_container_width=True, on_click=clear_all)

# ------------------------------------------------------------------ geração
# Roda ANTES de desenhar o campo de resultado, para poder preenchê-lo.

if st.session_state.pending:
    st.session_state.pending = False
    source = st.session_state.input_text
    try:
        with col_out, st.spinner(f"Reescrevendo no modo {MODES[mode].label}..."):
            result = rewrite(source, mode, protected_terms=protected_terms, settings=settings)
        st.session_state.output_text = result.text
        st.session_state.last_original = source
        st.session_state.last_mode = mode
        st.session_state.meta = result
    except InvalidInputError as exc:
        col_in.warning(str(exc))
    except HumanizerError as exc:
        col_out.error(str(exc))

# ------------------------------------------------------------------ resultado

with col_out:
    st.text_area(
        "Resultado (editável)",
        key="output_text",
        height=340,
        placeholder="O texto reescrito aparecerá aqui.",
    )
    output = st.session_state.output_text
    meta = st.session_state.meta
    if meta:
        st.caption(f"{len(output.split())} palavra(s) · {meta.duration_s:.1f} s · {meta.model}")
    else:
        st.caption(" ")

    c1, c2, c3 = st.columns(3)
    with c1.popover("📋 Copiar", use_container_width=True, disabled=not output):
        st.caption("Clique no ícone de copiar no canto do quadro:")
        st.code(output, language=None, wrap_lines=True)
    c2.download_button(
        "⬇️ Baixar .txt",
        data=output.encode("utf-8"),
        file_name="humanizabr_resultado.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not output,
    )
    c3.button("🔁 Reescrever de novo", use_container_width=True, on_click=request_rewrite,
              disabled=not st.session_state.input_text.strip())

# ------------------------------------------------------------------ verificações e comparação

if output and st.session_state.last_original:
    st.divider()
    original = st.session_state.last_original

    if st.session_state.input_text != original:
        st.info("O texto original foi alterado depois da última reescrita. "
                "A comparação abaixo usa a versão que gerou o resultado.")

    # Se o usuário editou o resultado, as verificações são refeitas sobre a versão editada.
    report = validate(original, output, st.session_state.last_mode or mode, protected_terms)

    tab_check, tab_style, tab_side, tab_diff = st.tabs(
        ["Verificações", "Estilo", "Lado a lado", "Diferenças"])

    with tab_check:
        if meta and meta.truncated:
            st.error("A geração atingiu o limite de tokens e pode estar incompleta. "
                     "Divida o texto ou aumente HUMANIZA_MAX_OUTPUT_TOKENS.")
        if not report.issues:
            st.success("Nenhuma alteração crítica encontrada pelas verificações automáticas. "
                       "Elas não garantem fidelidade total: revise o texto antes de usar.")
        for issue in report.issues:
            items = f" — `{'`, `'.join(issue.items)}`" if issue.items else ""
            show = st.error if issue.severity == CRITICAL else st.warning
            show(f"**{issue.category.capitalize()}:** {issue.message}{items}")
        st.caption(
            f"Similaridade com o original: {report.stats.get('similaridade', 0):.0%} · "
            f"Tamanho relativo: {report.stats.get('razao_tamanho', 0):.0%}"
        )

    with tab_style:
        so, sr = analyze(original), analyze(output)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Variação das frases", _fmt(sr.burstiness), _delta(sr.burstiness, so.burstiness),
                  help="Desvio padrão ÷ média do tamanho das frases. Mais alto = ritmo mais variado, "
                       "alternando frases curtas e longas. Precisa de 3 frases ou mais.")
        m2.metric("Variedade de vocabulário", _fmt(sr.diversity, pct=True),
                  _delta(sr.diversity, so.diversity, pct=True),
                  help="Fração de palavras diferentes (MATTR, janelas de 50 palavras). "
                       "Mais alto = menos repetição.")
        m3.metric("Voz passiva", sr.passive, sr.passive - so.passive or None, delta_color="inverse",
                  help="Construções como \"foi realizado\" (contagem aproximada).")
        m4.metric("Clichês", sr.cliche_total, sr.cliche_total - so.cliche_total or None,
                  delta_color="inverse", help="Expressões batidas, como \"além disso\" e \"essencial\".")
        st.caption("Os números pequenos mostram a diferença em relação ao original. São medidas "
                   "aproximadas de estilo: ajudam a revisar, mas não avaliam a qualidade do texto.")

        g1, g2 = st.columns(2, gap="large")
        if so.lengths:
            g1.markdown("**Palavras por frase — original**")
            g1.bar_chart(so.lengths, height=180, x_label="frase", y_label="palavras")
        if sr.lengths:
            g2.markdown("**Palavras por frase — resultado**")
            g2.bar_chart(sr.lengths, height=180, x_label="frase", y_label="palavras")

        if sr.cliches:
            st.markdown("**Clichês no resultado** (destacados):")
            st.markdown(f'<div class="hb-box">{highlight_cliches(output)}</div>',
                        unsafe_allow_html=True)
        else:
            st.success("Nenhum clichê da lista encontrado no resultado.")

    with tab_side:
        s1, s2 = st.columns(2, gap="large")
        s1.markdown("**Original**")
        s1.markdown(f'<div class="hb-box">{html.escape(original)}</div>', unsafe_allow_html=True)
        s2.markdown("**Resultado**")
        s2.markdown(f'<div class="hb-box">{html.escape(output)}</div>', unsafe_allow_html=True)

    with tab_diff:
        st.caption("Vermelho riscado: removido · Verde: acrescentado")
        st.markdown(f'<div class="hb-diff">{word_diff_html(original, output)}</div>',
                    unsafe_allow_html=True)
