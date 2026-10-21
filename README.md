# ✍️ HumanizaBR

Aplicativo **local** para reescrever textos em português brasileiro com modelos
de linguagem abertos. Sem assinatura, sem créditos, sem APIs pagas: o texto
nunca sai do seu computador.

Inspirado nas funcionalidades públicas de ferramentas como o BypassGPT, mas com
implementação própria. **Não** sabemos como essas ferramentas funcionam por
dentro e não tentamos reproduzi-las. O objetivo aqui é produzir textos naturais,
**fiéis ao original** e adequados ao contexto. O app **não promete** que um texto
passará por detectores de IA, e a nota desses detectores não é usada como
medida de qualidade.

## Funcionalidades

- 5 modos: **Natural e fluido**, **Acadêmico**, **Profissional**, **Conciso** e
  **Correção gramatical**.
- Resultado editável, botão de copiar, download em `.txt` e opção de reescrever de novo.
- Comparação **lado a lado** e **diferenças destacadas** palavra a palavra.
- **Verificações automáticas de fidelidade**: números, datas, citações,
  trechos entre aspas, URLs, siglas, nomes próprios, termos técnicos, termos
  protegidos pelo usuário, negações, grau de certeza, idioma e tamanho. Elas
  avisam sobre alterações possivelmente críticas em vez de declarar o texto "correto".
- Limite configurável de entrada, mensagens de erro compreensíveis, nada salvo em disco.

## Arquitetura

```
┌──────────────┐   texto + modo   ┌───────────────┐   HTTP local    ┌──────────────┐
│   app.py     │ ───────────────▶ │  humanizer.py │ ──────────────▶ │    Ollama    │
│ (Streamlit)  │ ◀─────────────── │ (prompt, erros│ ◀────────────── │ 127.0.0.1:   │
└──────┬───────┘   texto revisado │  e limpeza)   │                 │ 11434 (LLM)  │
       │                          └───────┬───────┘                 └──────────────┘
       │ original × resultado             │ usa
       ▼                                  ▼
┌──────────────┐                  ┌───────────────┐   ┌───────────┐
│validators.py │                  │   modes.py    │   │ config.py │
│ (fidelidade) │                  │ (instruções)  │   │ (ajustes) │
└──────────────┘                  └───────────────┘   └───────────┘
```

A interface **não** contém lógica de reescrita. Para trocar o Streamlit por
outra tecnologia, basta chamar `humanizer.rewrite()` e `validators.validate()`.

| Arquivo | Responsabilidade |
|---|---|
| [`app.py`](app.py) | Interface web: entrada, modos, resultado, cópia, download, comparação e alertas |
| [`humanizer.py`](humanizer.py) | Motor: valida a entrada, monta o prompt, chama o Ollama, trata erros, limpa a resposta |
| [`modes.py`](modes.py) | Regras gerais, instruções de cada modo e exemplo demonstrativo; `PROMPT_VERSION` |
| [`validators.py`](validators.py) | Verificações determinísticas entre original e resultado |
| [`config.py`](config.py) | Parâmetros (modelo, temperatura, limites), sobrescrevíveis por variáveis de ambiente |
| [`.streamlit/config.toml`](.streamlit/config.toml) | Interface só em `127.0.0.1` e telemetria do Streamlit desligada |
| [`tests/`](tests/) | Testes unitários, de interface e de integração |
| [`evaluation/`](evaluation/) | 34 exemplos de avaliação, script de avaliação e resultados |
| [`docs/AVALIACAO.md`](docs/AVALIACAO.md) | Resultados e achados dos experimentos |

### Decisões técnicas

- **Ollama** roda o modelo localmente e expõe uma API HTTP só nesta máquina.
  Ele cuida de GPU, quantização e cache do modelo, sem exigir código de CUDA.
- **Modelo padrão: `qwen3:4b-instruct-2507-q4_K_M`** (Apache 2.0, ~2,5 GB).
  A tag `qwen3:4b` aponta para a variante *Thinking*, que "raciocina" antes de
  cada resposta e levou ~80 s por frase. A variante *Instruct* responde em ~0,5 s.
- **Temperatura 0,4** (0,1 no modo Correção gramatical): variação de estilo
  suficiente sem "criatividade" que invente conteúdo.
- **Texto do usuário delimitado** por `<texto>…</texto>`, com regras na
  mensagem de sistema, um exemplo demonstrativo e um lembrete após o texto.
  Isso reduz, mas **não elimina**, o risco de o modelo obedecer a instruções
  escritas dentro do texto (*prompt injection*).
- **Verificações determinísticas primeiro**: comparar números ou citações com
  expressões regulares é barato, explicável e testável. Avaliar significado
  exige exemplos conhecidos e revisão humana.
- **Sem banco de dados, autenticação, Docker ou fine-tuning** no MVP: não houve
  necessidade concreta.

## Instalação (Windows)

Pré-requisitos: **Python 3.10+**, **Git** e cerca de **6 GB** livres (Ollama + modelo).
O projeto foi testado com Python 3.12 e Ollama 0.40.6.

```powershell
# 1. Ollama (uma vez). Instala o serviço local e um ícone na bandeja.
winget install --id Ollama.Ollama -e

# 2. Modelo (uma vez, ~2,5 GB)
ollama pull qwen3:4b-instruct-2507-q4_K_M

# 3. Projeto
cd C:\humanizador
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Se o PowerShell bloquear `Activate.ps1`, você pode chamar o Python do venv
> diretamente (`.\.venv\Scripts\python.exe ...`) sem mudar nenhuma política do
> sistema.

## Execução

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abra http://localhost:8501. O Ollama precisa estar ativo (ícone na bandeja ou
`ollama serve`). A barra lateral mostra se ele e o modelo estão disponíveis.

## Testes

```powershell
# Unitários + interface: não precisam de Ollama nem de internet (~3 s)
.\.venv\Scripts\python.exe -m pytest

# Integração: usam o Ollama e o modelo real (~10 s)
.\.venv\Scripts\python.exe -m pytest -m integration -v
```

| Conjunto | Arquivo | O que cobre |
|---|---|---|
| Unitário | `test_humanizer.py` | Entradas vazias/inválidas, modo inexistente, falha de conexão, timeout, modelo ausente, resposta vazia, cada modo, delimitação do texto, logs sem conteúdo, limpeza da resposta |
| Unitário | `test_validators.py` | Números, datas, nomes, siglas, citações, aspas, termos técnicos, negações, ressalvas, idioma, tamanho, alterações excessivas |
| Unitário | `test_modes.py` | Existência e consistência dos modos e das regras |
| Interface | `test_app.py` | App abre, reescreve, preserva textos entre interações, repassa o modo, mostra alertas e erros, limpa |
| Integração | `test_integration.py` | Os 5 modos, números/datas, nomes/siglas, citações, termos técnicos, texto curto, injeção, modelo inexistente, servidor inacessível |

**Última execução (2026-10-20):** 97 unitários/interface aprovados; 13 de
integração aprovados em 3 execuções seguidas.

## Avaliação de qualidade

```powershell
.\.venv\Scripts\python.exe evaluation\evaluate.py --runs 3              # modelo padrão
.\.venv\Scripts\python.exe evaluation\evaluate.py --model qwen3:8b      # outro modelo
.\.venv\Scripts\python.exe evaluation\evaluate.py --compare A.json B.json
.\.venv\Scripts\python.exe evaluation\evaluate.py --rescore evaluation\results\*.json
```

Cada execução grava, em `evaluation/results/`, um `.json` (para comparar
versões) e um `.md` (original × resultado, para revisão humana). O nome do
arquivo inclui modelo e `PROMPT_VERSION`. Ao alterar instruções em `modes.py`,
**incremente `PROMPT_VERSION`**.

Resultado atual: **87% de aprovação** nos critérios objetivos com o modelo
padrão (v1 do prompt: 76%), ~0,5 s por reescrita e 3,7 GB de VRAM. O
`qwen3:8b` chegou a **94%**, sem alertas críticos, usando 5,9 GB de VRAM.
Detalhes em [docs/AVALIACAO.md](docs/AVALIACAO.md).

## Trocar o modelo

Os parâmetros ficam em [`config.py`](config.py) e podem ser sobrescritos sem
editar código:

```powershell
ollama pull <modelo>
$env:HUMANIZA_MODEL = "<modelo>"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Para mais qualidade (veja o benchmark), use `qwen3:8b`: `ollama pull qwen3:8b`
e `$env:HUMANIZA_MODEL = "qwen3:8b"`. O raciocínio de modelos híbridos fica
desligado por padrão (`HUMANIZA_THINK`).

Outras variáveis: `HUMANIZA_TEMPERATURE`, `HUMANIZA_MAX_OUTPUT_TOKENS`,
`HUMANIZA_CONTEXT_WINDOW`, `HUMANIZA_MAX_INPUT_CHARS`, `HUMANIZA_TIMEOUT`,
`HUMANIZA_HOST`. Antes de adotar um modelo, rode a avaliação com ele e compare
com o atual.

## Privacidade e funcionamento offline

| Momento | Precisa de internet? |
|---|---|
| Instalar Python, Ollama e dependências (`pip`) | Sim |
| Baixar o modelo (`ollama pull`) | Sim |
| **Usar o app, rodar testes e avaliações** | **Não** |

Conexões usadas durante o uso:

- Navegador → Streamlit em `127.0.0.1:8501`.
- Streamlit (Python) → Ollama em `127.0.0.1:11434`.

Ambos escutam **apenas em 127.0.0.1**, então outros dispositivos da rede não
acessam. A telemetria do Streamlit está desligada (`gatherUsageStats = false`).
O projeto não tem telemetria própria, não salva histórico e registra nos logs
apenas metadados (modo, tamanho em caracteres, duração), nunca o conteúdo.
O aplicativo do Ollama na bandeja pode procurar atualizações na internet. A
geração de texto não depende disso.

**Verificação realizada:** durante uma avaliação, todas as conexões TCP dos
processos `python` e `ollama` foram listadas, e todas eram para `127.0.0.1`.

**Como verificar o modo offline você mesmo:**

1. Desconecte o Wi-Fi/cabo de rede.
2. `ollama list`: o modelo deve aparecer.
3. `.\.venv\Scripts\python.exe -m pytest -m integration`: todos devem passar.
4. Abra o app, reescreva um texto e confira o resultado.
5. Reconecte a rede.

## Limitações conhecidas

- **LLMs podem alterar ou omitir informações.** As verificações automáticas
  pegam muitos casos (números, citações, siglas...), mas não todos. Mudanças
  sutis de sentido exigem leitura humana. **Sempre revise o resultado.**
- As verificações são heurísticas. Há falsos positivos (ex.: "3 mil" → "3.000")
  e falsos negativos (ex.: "ainda não é possível afirmar" → "não é", sem alterar
  a contagem de negações).
- **Correção gramatical** é o modo mais fraco (60% na avaliação). O modelo de
  4B às vezes deixa passar erros ("Fazem dois anos") ou introduz vírgulas
  indevidas.
- **Injeção de instruções** foi reduzida, mas não eliminada. Quando o modelo
  traduz o texto ou escreve algo muito mais longo, o app emite alerta crítico.
- O modo Acadêmico às vezes expande siglas por conta própria (OMS → Organização
  Mundial da Saúde). O app avisa.
- Textos acima do limite (6.000 caracteres por padrão) precisam ser divididos
  manualmente.
- Números por extenso compostos ("vinte e cinco") não são reconhecidos pelo validador.

## Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| "Não foi possível conectar ao Ollama" | Ollama não está rodando | Abra o Ollama pelo menu Iniciar ou rode `ollama serve` |
| "Modelo ... não está disponível" | Modelo não baixado | `ollama pull qwen3:4b-instruct-2507-q4_K_M` |
| `ollama` não é reconhecido no terminal | PATH não atualizado após instalar | Feche e reabra o terminal |
| Resposta muito lenta (dezenas de segundos) | Modelo *Thinking* ou rodando na CPU | Use a variante *Instruct*; confira `ollama ps` (coluna PROCESSOR deve mostrar GPU) |
| "atingiu o limite de tokens" | Texto longo | Divida o texto ou aumente `HUMANIZA_MAX_OUTPUT_TOKENS` |
| `UnicodeEncodeError` ao rodar scripts | Console do Windows em cp1252 | `$env:PYTHONIOENCODING = "utf-8"` |
| Porta 8501 ocupada | Outro Streamlit aberto | Feche-o ou use `--server.port 8502` |

Para diagnosticar, os logs no terminal do Streamlit mostram modo, tamanho,
tokens gerados, duração e motivo de término de cada geração.

## Licenças

| Componente | Licença |
|---|---|
| Qwen3-4B-Instruct-2507 | Apache 2.0 |
| Ollama | MIT |
| Streamlit | Apache 2.0 |
| ollama-python | MIT |
| httpx | BSD-3-Clause |
| pytest | MIT |

## Roteiro

1. **Benchmark:** medir de novo a latência do `qwen3:8b` com a GPU livre e
   testar `mistral:7b`, `gemma3:4b` e `llama3.1:8b` com o mesmo conjunto.
2. **Revisão humana** dos relatórios em `evaluation/results/*.md`.
3. Controle de intensidade da reescrita e de tamanho desejado.
4. Divisão automática de textos longos por parágrafo.
5. Importação de arquivos `.txt`/`.docx`.
6. Histórico local **opcional**, com consentimento explícito.
7. Fine-tuning apenas se houver dados adequados e um ganho que justifique o custo.
