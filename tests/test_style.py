import pytest

from style import (
    analyze,
    burstiness,
    cliche_spans,
    find_ai_patterns,
    find_cliches,
    lexical_diversity,
    new_ai_patterns,
    new_cliches,
    passive_count,
    split_sentences,
)


def test_divide_frases():
    assert split_sentences("Primeira frase. Segunda! Terceira?\nQuarta") == [
        "Primeira frase.", "Segunda!", "Terceira?", "Quarta"]


def test_numero_decimal_nao_divide_frase():
    assert len(split_sentences("A taxa foi de 12,5% e o valor 1.245 reais.")) == 1


def test_burstiness_zero_quando_frases_iguais():
    assert burstiness("Eu gosto de café. Ela gosta de chá. Nós vamos ao mar.") == pytest.approx(0)


def test_burstiness_maior_com_frases_variadas():
    uniforme = "Eu gosto de café. Ela gosta de chá. Nós vamos ao mar."
    variado = ("Pronto. Depois de uma semana inteira de testes e ajustes no servidor, "
               "a equipe finalmente liberou a nova versão. Funcionou.")
    assert burstiness(variado) > burstiness(uniforme)


def test_burstiness_precisa_de_tres_frases():
    assert burstiness("Uma frase. Outra frase.") is None


def test_diversidade_penaliza_repeticao():
    repetido = "o texto o texto o texto o texto o texto o texto"
    variado = "cada palavra aqui aparece somente uma vez neste exemplo curto"
    assert lexical_diversity(variado) > lexical_diversity(repetido)


def test_diversidade_texto_curto_demais():
    assert lexical_diversity("Oi, tudo bem?") is None


@pytest.mark.parametrize("texto, n", [
    ("O relatório foi revisado pela equipe.", 1),
    ("Os dados foram coletados e serão analisados.", 2),
    ("O contrato foi feito ontem.", 1),
    ("A equipe revisou o relatório.", 0),
])
def test_voz_passiva(texto, n):
    assert passive_count(texto) == n


def test_encontra_cliches_sem_diferenciar_maiusculas():
    texto = "Além disso, é fundamental. Vale ressaltar que isso é essencial e fundamental."
    assert find_cliches(texto) == {"além disso": 1, "fundamental": 2, "vale ressaltar": 1, "essencial": 1}


def test_cliche_exige_palavra_inteira():
    assert find_cliches("Os fundamentos e a essência do assunto.") == {}


def test_nao_so_mas_tambem():
    assert "não só... mas também" in find_cliches("Ajuda não só alunos, mas também professores.")


def test_novos_cliches_ignora_os_do_original():
    original = "É essencial revisar o texto."
    assert new_cliches(original, "É essencial revisar o texto.") == {}
    assert new_cliches(original, "Além disso, é essencial e crucial revisar.") == {
        "além disso": 1, "crucial": 1}


def test_cliche_spans_cobrem_o_trecho():
    texto = "Em suma, foi bom."
    (s, e), = cliche_spans(texto)
    assert texto[s:e] == "Em suma"


def test_analyze_resume_tudo():
    r = analyze("Além disso, o texto foi revisado. Ficou ótimo. Todo mundo leu com calma no fim de semana.")
    assert r.sentences == 3 and r.lengths == [6, 2, 9]
    assert r.passive == 1 and r.cliche_total == 1
    assert set(r.to_dict()) >= {"variacao_frases", "variedade_vocabulario", "cliches", "padroes_ia"}


@pytest.mark.parametrize("texto, padrao", [
    ("Não é só importante. É vida.", '"Não é só X. É Y."'),
    ("Ler não é só uma atividade — é um passo.", '"Não é só X. É Y."'),
    ("Não é mais só futuro. É agora.", '"Não é só X. É Y."'),
    ("E o melhor? O plano custa R$ 99.", "pergunta de efeito"),
    ("As vendas caíram. O resultado? Prejuízo.", "pergunta de efeito"),
    ("É o que nos move, nos transforma, nos torna quem somos.", "trio repetitivo"),
    ("Integra com o ERP — sem burocracia. Relatórios — sem esperar.", "travessões em excesso"),
])
def test_padroes_de_ia(texto, padrao):
    assert padrao in find_ai_patterns(texto)


@pytest.mark.parametrize("texto", [
    "Qual é a capital da França, segundo o questionário?",
    "Atua na saúde, na educação e no comércio.",
    "Não é possível afirmar. É provável que sim.",
    "Um único travessão — como este — é aceitável.",
])
def test_textos_comuns_nao_sao_padroes_de_ia(texto):
    assert find_ai_patterns(texto) == {}


def test_novos_padroes_ignora_os_do_original():
    assert new_ai_patterns("Fala, chefe. Blz?", "Fala, chefe. Blz?") == {}
    assert new_ai_patterns("O plano custa R$ 99.", "E o melhor? O plano custa R$ 99.") == {
        "pergunta de efeito": 1}


def test_padroes_de_ia_aparecem_no_relatorio_e_nos_destaques():
    texto = "Não é só bom. É ótimo."
    assert analyze(texto).ai_pattern_total == 1
    assert cliche_spans(texto)
