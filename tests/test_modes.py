import pytest

from modes import BASE_RULES, MODES, PROMPT_VERSION, get_mode

EXPECTED = {"natural", "academico", "profissional", "conciso", "gramatica"}


def test_os_cinco_modos_existem():
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
