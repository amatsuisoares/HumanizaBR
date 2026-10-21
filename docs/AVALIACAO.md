# Avaliação do HumanizaBR

Registro dos experimentos de prompt e modelo. Os arquivos brutos (JSON e
Markdown para revisão humana) estão em [`evaluation/results/`](../evaluation/results/).

## Metodologia

- **Conjunto:** 34 exemplos em [`evaluation/examples.json`](../evaluation/examples.json),
  em 12 categorias (números e datas, nomes e siglas, citações acadêmicas, termos
  técnicos, textos curtos, ressalvas, negação, linguagem informal, correção
  gramatical, injeção de instruções, listas, textos profissionais/acadêmicos),
  cobrindo os 5 modos.
- **Critérios objetivos por exemplo:** `must_keep` (trecho exato), `must_keep_any`
  (ao menos uma alternativa por grupo), `must_not_contain` e, para todos, saída
  com no máximo 2,5× o tamanho do original.
- **Execuções:** 3 por exemplo (102 gerações). *Estabilidade* = fração de
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
