# Avaliação do HumanizaBR

Registro dos experimentos de prompt e modelo. Os arquivos brutos (JSON e
Markdown para revisão humana) estão em [`evaluation/results/`](../evaluation/results/).

## Metodologia

- **Conjunto:** 40 exemplos em [`evaluation/examples.json`](../evaluation/examples.json),
  em 13 categorias (expressivo, números e datas, nomes e siglas, citações acadêmicas, termos
  técnicos, textos curtos, ressalvas, negação, linguagem informal, correção
  gramatical, injeção de instruções, listas, textos profissionais/acadêmicos),
  cobrindo os 6 modos.
- **Critérios objetivos por exemplo:** `must_keep` (trecho exato), `must_keep_any`
  (ao menos uma alternativa por grupo), `must_not_contain` e, para todos, saída
  com no máximo 2,5× o tamanho do original.
- **Execuções:** 3 por exemplo (120 gerações; 102 até a v4). *Estabilidade* = fração de
  exemplos com o mesmo resultado (aprovado/reprovado) nas 3 execuções.
- **Hardware:** Ryzen 7 5700X, RTX 5060 8 GB, 32 GB RAM, Windows 11, Ollama 0.40.6.
- Todas as versões foram **re-pontuadas com o mesmo gabarito final**
  (`evaluate.py --rescore`), para a comparação ser justa.

## Resultados — `qwen3:4b-instruct-2507-q4_K_M`

| Prompt | Aprovação | Natural | Acadêmico | Profissional | Conciso | Gramática | Alertas críticos/ex. | Estabilidade | Latência média |
|---|---|---|---|---|---|---|---|---|---|
| v1 | 76% | 62% | 86% | 100% | 67% | 60% | 0,12 | 1,00 | 0,45 s |
| v2 | 83% | 75% | 86% | 100% | 89% | 60% | 0,07 | 0,97 | 0,45 s |
| v3 | 88% | 100% | 86% | 88% | 100% | 60% | 0,03 | 1,00 | 0,46 s |
| **v4** (atual) | **87%** | 96% | 86% | 88% | 100% | 60% | 0,03 | 0,97 | 0,46 s |

Uso de VRAM: 3,7 GB em todas as versões (contexto de 8.192 tokens).

Com 34 exemplos, cada exemplo vale ~3 pontos percentuais: v3 e v4 são
estatisticamente equivalentes.

### O que cada versão mudou

- **v2** — regras explícitas para manter siglas, marcações de referência
  (`[1]`, `(AUTOR, ano)`), aspas e código entre crases; ressalvas no modo Conciso.
  Corrigiu: referências apagadas (`cit-03`), código desformatado (`tec-02`),
  aspas removidas (`cit-02`).
- **v3** — exemplo demonstrativo (*few-shot*) + lembrete após o texto contra
  instruções embutidas. Corrigiu a injeção `inj-01` ("escreva um poema"), que
  na v1/v2 funcionava em **6 de 6** execuções.
- **v4** — retirou a brecha "a menos que o texto exija outro idioma" da regra de
  idioma. Não teve efeito mensurável no `inj-02`.

## Benchmark de modelos (prompt v4)

| Modelo | Licença | Aprovação | Natural | Acadêmico | Profissional | Conciso | Gramática | Alertas críticos/ex. | Estabilidade | VRAM |
|---|---|---|---|---|---|---|---|---|---|---|
| `qwen3:4b-instruct-2507-q4_K_M` | Apache 2.0 | 87% | 96% | 86% | 88% | 100% | 60% | 0,03 | 0,97 | 3,7 GB |
| `qwen3:8b` (`think=False`) | Apache 2.0 | **94%** | 92% | 100% | 96% | 100% | 80% | **0** | 0,94 | 5,9 GB |

- O 8B resolveu as duas injeções (`inj-01`, `inj-02`), a expansão indevida de
  sigla (`nom-04`) e a vírgula indevida (`cur-01`).
- O 8B falhou em `inf-02`: trocou "mando amanhã cedo" por "assim que possível,
  com certa antecedência". É uma **alteração de conteúdo não detectada** pelo validador.
- Nenhum dos dois corrige "Fazem dois anos" (`gra-01`).
- **Latência não comparável.** O benchmark do 8B rodou com jogos abertos
  disputando a GPU (53% de uso em repouso). Nessas condições, até o 4B caiu de
  ~110 para ~25 tokens/s. A latência medida do 8B (média de 8,7 s) **não
  representa** o desempenho real e precisa ser medida de novo com a GPU livre.
  Medição isolada com a GPU disputada: 8B a 4–5 tokens/s com contexto de 8.192
  e 11–12 tokens/s com contexto de 4.096 (o cache menor libera VRAM).

**Decisão (prompt v4):** o 4B continuou como padrão por ser mais rápido e por
caber com folga em GPUs de 6 GB (ex.: RTX 4050). Depois da revisão humana de
2026-10-21 (ver abaixo), o **8B passou a ser o padrão**; o 4B ficou como opção
leve: `$env:HUMANIZA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"`.

Modelos considerados e não testados: `mistral:7b` (Apache 2.0, 4,4 GB),
`gemma3:4b` (Gemma Terms of Use, 3,4 GB) e `llama3.1:8b` (Llama 3.1 Community
License, 4,9 GB).

## Modo Expressivo e métricas de estilo (prompts v5 e v6)

Objetivo: textos com mais variação no tamanho das frases, vocabulário mais
variado, voz ativa, tom levemente coloquial, no máximo uma metáfora e sem
clichês ("além disso", "essencial", "fundamental"...). Para medir isso, foram
criados 6 exemplos `exp-*` (textos cheios de clichês, voz passiva e frases
repetitivas) e as métricas de [`style.py`](../style.py), registradas para
todos os modos.

- **v5:** regra 13 em todos os modos ("não introduza clichês") e o modo
  Expressivo (temperatura 0,8).
- **v6:** o Expressivo passou a exigir uma frase bem curta e a proteger
  palavras-chave do assunto, negações e gramática. Motivo: na v5, o 4B trocou
  "não foi aprovado" por "foi rejeitado", "educação" por "escola", e escreveu
  "habitude" e "não todos" (no lugar de "nem todos").

| Modelo / prompt | Aprovação nos 5 modos originais | Aprovação no Expressivo | Variação das frases (orig. → result.) | Vocabulário | Voz passiva/ex. | Clichês/ex. | Clichês novos/ex. (todos os modos) |
|---|---|---|---|---|---|---|---|
| 4B / v4 | 87% | — | — | — | — | — | 0 |
| 4B / v5 | 87% | 39% | 0,33 → 0,32 | 0,87 → 0,90 | 1,5 → 0,6 | 2,2 → 0,1 | 0 |
| 4B / v6 | 85% | 61% | 0,33 → 0,35 | 0,87 → 0,89 | 1,5 → 0,7 | 2,2 → 0,06 | 0,008 |
| 8B / v6 | 94% | 67% | 0,33 → **0,23** | 0,87 → 0,93 | 1,5 → 0,4 | 2,2 → 0,39 | 0,04 |

(As colunas de estilo são médias dos exemplos do Expressivo. "Variação das
frases" só é calculada com 3 frases ou mais.)

O que os números mostram:

- **Clichês e voz passiva caíram bastante** nos dois modelos. Nos outros modos,
  a regra 13 praticamente zerou os clichês introduzidos pelo modelo.
- **A variação no tamanho das frases quase não mudou.** O 4B ficou em torno do
  original, e o 8B produziu frases *mais* uniformes. Instrução em texto,
  sozinha, não garante esse aspecto em modelos deste tamanho.
- **O 4B é mais "ousado", mas menos fiel:** troca o sentido de negações e
  palavras-chave. O **8B é mais fiel, mas mais conservador**: às vezes copia o
  clichê do original ("Além disso, é importante lembrar...").
- Nos 5 modos originais, a v6 não piorou de forma mensurável (85% × 87% é
  menos de um exemplo de diferença). Uma exceção: o 4B passou a manter "Blz?"
  no `inf-02` (modo Profissional) nas 3 execuções.
- Critérios corrigidos: aceitar "assegurada" como equivalente a "garantida"
  (`res-03`), "instantânea" a "tempo real" (`exp-05`) e paráfrases fiéis em
  `exp-04`/`exp-06` ("não passou pela aprovação", "não confirmam ainda",
  "nem todas"). Todas as versões foram re-pontuadas com o gabarito final.

**Latência do 8B medida de novo com a GPU livre:** média de 0,75 s (máximo de
6,7 s, no carregamento do modelo), contra 0,45 s do 4B. A medição anterior
(8,7 s) tinha sido feita com jogos disputando a GPU.

## `qwen3:30b-a3b-instruct-2507-q4_K_M` (prompt v6)

Modelo de 30,5B parâmetros do tipo *mixture of experts* (~3B ativos por
token), Apache 2.0, 18,6 GB. Não cabe nos 8 GB da RTX 5060: o Ollama coloca
~6 GB na GPU e o restante na RAM. Primeira carga: ~41 s; depois, ~2,5 s por
reescrita.

| Modelo / prompt | 5 modos originais | Gramática | Expressivo | Variação das frases no Expressivo (orig. 0,33) | Clichês no Expressivo (orig. 2,2) | Estabilidade | Latência média |
|---|---|---|---|---|---|---|---|
| 4B / v6 | 85% | 60% | 61% | 0,35 | 0,06 | 0,93 | 0,45 s |
| 8B / v6 | 94% | 80% | 67% | 0,23 | 0,39 | 0,95 | 0,75 s |
| 30B-A3B / v6 | **96%** | **100%** | 61% | **0,53** | 0,28 | 0,88 | 2,5 s |

- O 30B corrigiu o `gra-01` ("Fazem dois anos" → "Faz dois anos") e o
  `cur-01`, falhas que 4B e 8B nunca resolveram.
- No Expressivo, o 30B é o único com variação de ritmo de verdade, mas
  **enfeita**: "Isso não é futuro. É agora.", "É vida. Ler é viver mais.",
  "Economia com qualidade." Esse tipo de acréscimo só é pego pela avaliação
  quando aumenta muito o tamanho do texto.
- Falhas do 30B nos outros modos: troca "provavelmente" por "há possibilidade"
  (`res-03`, ressalva enfraquecida, com aviso do validador) e, em 1 de 3
  execuções, "uma hora" por "vinte minutos" (`inf-01`, alerta crítico).

**Revisão humana (2026-10-21), usando o app:** o 8B foi considerado superior
ao 30B. No Acadêmico, o 30B soou "mais artificial". No Expressivo, ele
"removeu muitas informações" e as escolhas de frase deixaram o texto
"robótico, como uma versão antiga do ChatGPT". As métricas automáticas
apontavam o 30B como melhor, mas a leitura humana discordou. Padrões nas
saídas do 30B que explicam essa impressão, e que a lista de clichês (só
palavras e expressões) não detectava: "Não é só X. É Y.", travessões em
excesso, perguntas de efeito ("E o melhor?") e sequências de três ("nos move,
nos transforma, nos torna quem somos"). **Decisão:** o 30B foi descartado e o
8B passou a ser o modelo padrão.

Um ajuste de prompt testado depois da v6 (temperatura 0,7 e proibição de
frases acrescentadas no Expressivo) também foi **descartado**: na revisão
humana, os modos Expressivo e Profissional ficaram piores que na v6.

## Padrões de IA (detecção) e prompt v8 (descartado)

A partir da revisão humana do 30B, o [`style.py`](../style.py) passou a
detectar quatro estruturas que soam artificiais: "Não é só X. É Y.", perguntas
curtas de efeito ("E o melhor?"), trios com a mesma palavra inicial e mais de
uma frase com travessão. A aba "Estilo" mostra a contagem, e o validador avisa
quando o resultado introduz algum desses padrões.

Padrões de IA introduzidos por texto (média em todos os modos, prompt v6): 4B
0,03 · 8B 0,02 · **30B 0,10**. Isso confirma que eram um problema
principalmente do 30B.

A **v8** acrescentou ao prompt uma regra contra esses padrões. Com o 8B, ela
zerou os padrões introduzidos (de 0,02 para 0), mas a aprovação nos 5 modos
originais caiu de 94% para 91%: o `tec-02` perdeu "venv" e o `cit-01` piorou.
A diferença está perto do ruído de medição, porém sem ganho que a justifique.
**Decisão:** manter o prompt da v6 e usar os padrões apenas na detecção.

## Achados importantes

1. **A tag `qwen3:4b` é a variante *Thinking*.** Ela raciocina sempre, ignora
   `think=False` (o raciocínio vaza para a resposta, em inglês) e levou ~80 s
   para reescrever uma frase. A variante *Instruct-2507* do mesmo modelo responde
   em ~0,5 s.
2. **A avaliação também tem bugs.** Na primeira versão, o exemplo de injeção era
   marcado como aprovado mesmo quando o modelo escrevia o poema, porque os
   termos proibidos escolhidos ("miau", "felino") não apareciam. A correção foi
   o critério global de tamanho (2,5×), calibrado com as saídas reais: a maior
   razão entre saídas legítimas foi 1,48.
3. **Defesas contra injeção interagem.** O exemplo demonstrativo da v3 resolveu
   `inj-01`, mas passou a fazer o modelo traduzir parcialmente o `inj-02`
   ("Responda em inglês: ..."). Nesse caso, o validador emite alerta **crítico**
   de idioma, e o usuário é avisado.

## Falhas que persistem (v4)

| Exemplo | Problema | Detectado pelo validador? |
|---|---|---|
| `nom-04` | Expande "OMS" para "Organização Mundial da Saúde" e acrescenta o nome do CDC | Sim (aviso: sigla e nomes novos) |
| `cur-01` | Correção gramatical **introduz** erro: "Bom dia, a todos." | Não |
| `gra-01` | Não corrige "Fazem dois anos" (verbo impessoal) | Não |
| `inj-02` | Traduz parte do texto para o inglês quando o texto pede | Sim (crítico: idioma) |

Erros gramaticais sutis não são detectáveis por regras simples: dependem de
revisão humana ou de um modelo maior (ver benchmark).

## Revisão humana

Os arquivos `.md` em `evaluation/results/` trazem original × resultado de cada
exemplo, com espaço para notas de 1 a 5 em **fidelidade**, **fluência** e
**adequação ao modo**. A revisão humana ainda **não foi feita**.
