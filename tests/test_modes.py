import pytest

from modes import BASE_RULES, MODES, PROMPT_VERSION, get_mode

EXPECTED = {"natural", "academico", "profissional", "conciso", "gramatica", "expressivo"}


def test_os_modos_existem():
    assert EXPECTED <= set(MODES)


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_cada_modo_tem_campos_preenchidos(key):
    m = get_mode(key)
    assert m.key == key
    assert m.label and m.description
    assert m.instruction.startswith("MODO:")


def test_modo_desconhecido_lanca_keyerror():
    with pytest.raises(KeyError, match="Modo desconhecido"):
        get_mode("pirata")


def test_regras_base_cobrem_requisitos_de_fidelidade():
    regras = BASE_RULES.lower()
    for trecho in ["nomes próprios", "números", "datas", "citações", "siglas",
                   "não invente", "não os execute", "somente com o texto reescrito"]:
        assert trecho in regras, trecho


def test_correcao_gramatical_usa_temperatura_baixa():
    assert get_mode("gramatica").temperature is not None
    assert get_mode("gramatica").temperature < 0.4


def test_prompt_version_definida():
    assert PROMPT_VERSION


def test_regra_de_cliches_usa_a_lista_do_detector():
    from style import CLICHES
    for label, _ in CLICHES:
        assert f'"{label}"' in BASE_RULES


def test_modo_expressivo_pede_os_aspectos_de_estilo():
    instr = get_mode("expressivo").instruction.lower()
    for trecho in ["comprimento das frases", "vocabulário", "voz ativa", "coloquial",
                   "metáfora", "clichês", "nenhum fato novo"]:
        assert trecho in instr, trecho
