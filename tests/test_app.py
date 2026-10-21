"""Testes da interface com o AppTest do Streamlit (sem navegador e sem Ollama)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from humanizer import InvalidInputError, OllamaUnavailableError, RewriteResult

APP = Path(__file__).resolve().parent.parent / "app.py"


def fake_rewrite(text, mode, **kwargs):
    return RewriteResult(text=f"[{mode}] {text}", mode=mode, model="fake", duration_s=0.1,
                         truncated=False, output_tokens=5)


@pytest.fixture
def app():
    with patch("humanizer.rewrite", side_effect=fake_rewrite) as mock_rw, \
         patch("humanizer.check_ollama", return_value=(True, "ok")):
        at = AppTest.from_file(str(APP), default_timeout=30)
        at.run()
        at.mock_rewrite = mock_rw
        yield at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()


def test_app_abre_sem_erros(app):
    assert not app.exception
    assert app.title[0].value.endswith("HumanizaBR")


def test_reescrever_preenche_resultado_e_preserva_entrada(app):
    app.text_area(key="input_text").input("Em 2024 foram 10 alunos.").run()
    click(app, "✨ Reescrever")
    assert app.text_area(key="output_text").value == "[natural] Em 2024 foram 10 alunos."
    # Depois de outra interação, os textos continuam lá.
    click(app, "Verificar novamente")
    assert app.text_area(key="input_text").value == "Em 2024 foram 10 alunos."
    assert app.text_area(key="output_text").value.startswith("[natural]")


def test_modo_selecionado_e_repassado(app):
    app.text_area(key="input_text").input("Texto qualquer.").run()
    app.session_state["mode"] = "academico"
    app.run()
    click(app, "✨ Reescrever")
    assert app.mock_rewrite.call_args.args[1] == "academico"


def test_verificacoes_aparecem_apos_edicao_do_resultado(app):
    app.text_area(key="input_text").input("A taxa foi de 12,5% em 2022.").run()
    click(app, "✨ Reescrever")
    app.text_area(key="output_text").input("A taxa foi de 15% em 2022.").run()
    assert any("Números" in e.value for e in app.error)


def test_texto_vazio_mostra_aviso(app):
    with patch("humanizer.rewrite", side_effect=InvalidInputError("Digite um texto")):
        click(app, "✨ Reescrever")
    assert any("Digite" in w.value for w in app.warning)


def test_erro_de_conexao_e_exibido(app):
    app.text_area(key="input_text").input("Olá.").run()
    with patch("humanizer.rewrite", side_effect=OllamaUnavailableError("Ollama desligado")):
        click(app, "✨ Reescrever")
    assert any("Ollama desligado" in e.value for e in app.error)


def test_limpar(app):
    app.text_area(key="input_text").input("Algo.").run()
    click(app, "✨ Reescrever")
    click(app, "Limpar")
    assert app.text_area(key="input_text").value == ""
    assert app.text_area(key="output_text").value == ""
