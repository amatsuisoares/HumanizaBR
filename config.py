"""Configuração central do HumanizaBR.

Todos os parâmetros ajustáveis ficam aqui, em um único lugar. Cada valor pode
ser sobrescrito por uma variável de ambiente, sem editar o código. Exemplo no
PowerShell:

    $env:HUMANIZA_MODEL = "qwen3:8b"
    streamlit run app.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Modelo usado pelo Ollama (precisa estar baixado: `ollama pull <nome>`).
    # Atenção: a tag "qwen3:4b" é a variante *Thinking*, que sempre "raciocina"
    # antes de responder (lenta para reescrita). Usamos a variante Instruct.
    model: str = "qwen3:4b-instruct-2507-q4_K_M"
    # Endereço do servidor Ollama. 127.0.0.1 = somente esta máquina.
    host: str = "http://127.0.0.1:11434"
    # Temperatura moderada: alguma variação de estilo, sem "criatividade" demais.
    temperature: float = 0.4
    top_p: float = 0.9
    # Limite de tokens gerados na saída (num_predict no Ollama).
    max_output_tokens: int = 2048
    # Janela de contexto (prompt + resposta), em tokens.
    context_window: int = 8192
    # Limite de caracteres aceitos na entrada, para controlar memória/tempo.
    max_input_chars: int = 6000
    # Tempo máximo de espera por uma resposta do modelo, em segundos.
    timeout_seconds: float = 300.0
    # Modo de "raciocínio" de modelos híbridos (ex.: qwen3:8b). Desligado: para
    # reescrita, raciocinar custa muito tempo e não trouxe ganho observável.
    think: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        return cls(
            model=_env_str("HUMANIZA_MODEL", d.model),
            host=_env_str("HUMANIZA_HOST", d.host),
            temperature=_env_float("HUMANIZA_TEMPERATURE", d.temperature),
            top_p=_env_float("HUMANIZA_TOP_P", d.top_p),
            max_output_tokens=_env_int("HUMANIZA_MAX_OUTPUT_TOKENS", d.max_output_tokens),
            context_window=_env_int("HUMANIZA_CONTEXT_WINDOW", d.context_window),
            max_input_chars=_env_int("HUMANIZA_MAX_INPUT_CHARS", d.max_input_chars),
            timeout_seconds=_env_float("HUMANIZA_TIMEOUT", d.timeout_seconds),
            think=_env_str("HUMANIZA_THINK", str(d.think)).lower() in ("1", "true", "sim"),
        )
