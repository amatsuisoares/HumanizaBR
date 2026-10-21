"""Avaliação reprodutível do HumanizaBR.

Roda todos os exemplos de evaluation/examples.json com um modelo e uma versão
de prompt, aplica verificações objetivas e salva os resultados em
evaluation/results/ (JSON para comparar + Markdown para revisão humana).

Uso (na raiz do projeto, com o venv ativo):

    python evaluation/evaluate.py                        # modelo padrão
    python evaluation/evaluate.py --model qwen3:8b       # outro modelo
    python evaluation/evaluate.py --runs 3               # mede estabilidade
    python evaluation/evaluate.py --ids res-01 inj-01    # só alguns exemplos
    python evaluation/evaluate.py --compare A.json B.json
    python evaluation/evaluate.py --rescore evaluation/results/*.json

Critérios objetivos de cada exemplo:
  - must_keep: trechos que devem aparecer exatamente (maiúsculas importam);
  - must_keep_any: grupos de alternativas; ao menos uma de cada grupo deve
    aparecer (sem diferenciar maiúsculas);
  - must_not_contain: trechos proibidos (indicam erro ou instrução obedecida);
  - tamanho: no máximo MAX_LENGTH_RATIO (ou max_length_ratio do exemplo) vezes
    o número de palavras do original;
  - alertas críticos do validators.py (contados, não reprovam sozinhos).

Métricas de estilo (style.py), medidas à parte e sem reprovar exemplos:
variação do tamanho das frases, variedade de vocabulário, voz passiva e
clichês, no original e no resultado.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import Settings  # noqa: E402
from humanizer import HumanizerError, make_client, rewrite  # noqa: E402
from modes import PROMPT_VERSION  # noqa: E402
from style import analyze, new_cliches  # noqa: E402
from validators import validate  # noqa: E402

EXAMPLES = Path(__file__).with_name("examples.json")
RESULTS_DIR = Path(__file__).with_name("results")
MAX_LENGTH_RATIO = 2.5


def load_examples(ids: list[str] | None = None) -> list[dict]:
    examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    if ids:
        examples = [e for e in examples if e["id"] in ids]
    return examples


def check_example(example: dict, output: str) -> list[str]:
    """Devolve a lista de critérios que falharam (vazia = aprovado)."""
    failures = []
    low = output.lower()
    for s in example.get("must_keep", []):
        if s not in output:
            failures.append(f"faltou: {s}")
    for group in example.get("must_keep_any", []):
        if not any(alt.lower() in low for alt in group):
            failures.append(f"faltou um de: {' | '.join(group)}")
    for s in example.get("must_not_contain", []):
        if s.lower() in low:
            failures.append(f"proibido: {s}")
    # Critério global: nas saídas legítimas medidas, a maior razão foi ~1,5.
    # Bem acima disso, o modelo provavelmente obedeceu a uma instrução do texto
    # ou inventou conteúdo.
    # Um exemplo pode exigir um limite mais rígido (max_length_ratio).
    ratio = len(output.split()) / max(1, len(example["text"].split()))
    if ratio > example.get("max_length_ratio", MAX_LENGTH_RATIO):
        failures.append(f"resultado {ratio:.1f}x mais longo que o original")
    return failures


STYLE_KEYS = ["variacao_frases", "variedade_vocabulario", "voz_passiva", "cliches"]


def style_metrics(original: str, output: str) -> dict:
    """Métricas de estilo do original (_in) e do resultado (_out)."""
    if not output:
        return {}
    a, b = analyze(original).to_dict(), analyze(output).to_dict()
    metrics = {f"{k}_in": a[k] for k in STYLE_KEYS} | {f"{k}_out": b[k] for k in STYLE_KEYS}
    metrics["cliches_novos"] = sum(new_cliches(original, output).values())
    return metrics


def vram_usage_mb(client, model: str) -> int | None:
    try:
        for m in client.ps().models:
            if m.model == model:
                return m.size_vram // 2**20
    except Exception:  # diagnóstico opcional; não deve derrubar a avaliação
        return None
    return None


def run_evaluation(settings: Settings, examples: list[dict], runs: int) -> dict:
    client = make_client(settings)
    records = []
    total = len(examples) * runs
    for run in range(1, runs + 1):
        for ex in examples:
            n = len(records) + 1
            try:
                res = rewrite(ex["text"], ex["mode"], settings=settings, client=client)
                output, error = res.text, None
                duration, tokens, truncated = res.duration_s, res.output_tokens, res.truncated
            except HumanizerError as exc:
                output, error, duration, tokens, truncated = "", str(exc), None, None, False

            failures = check_example(ex, output) if not error else ["erro de geração"]
            report = validate(ex["text"], output, ex["mode"]) if output else None
            records.append({
                "id": ex["id"], "category": ex["category"], "mode": ex["mode"], "run": run,
                "input": ex["text"], "output": output, "error": error,
                "duration_s": round(duration, 2) if duration is not None else None,
                "output_tokens": tokens, "truncated": truncated,
                "passed": not failures, "failures": failures,
                "critical_alerts": len(report.critical) if report else None,
                "warnings": len(report.warnings) if report else None,
                "alerts": [f"{i.severity}:{i.category}:{', '.join(i.items)}" for i in report.issues] if report else [],
                "stats": report.stats if report else {},
                "style": style_metrics(ex["text"], output),
            })
            status = "OK " if not failures else "FALHOU"
            print(f"[{n:>3}/{total}] {status} {ex['id']:<8} {ex['mode']:<12} "
                  f"{(duration or 0):5.1f}s  {'; '.join(failures)}")

    return {
        "meta": {
            "model": settings.model,
            "prompt_version": PROMPT_VERSION,
            "temperature": settings.temperature,
            "runs": runs,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "vram_mb": vram_usage_mb(client, settings.model),
        },
        "summary": summarize(records),
        "records": records,
    }


def summarize(records: list[dict]) -> dict:
    def rate(rs):
        return round(sum(r["passed"] for r in rs) / len(rs), 3) if rs else None

    durations = [r["duration_s"] for r in records if r["duration_s"] is not None]
    by = lambda key: {k: rate([r for r in records if r[key] == k])  # noqa: E731
                      for k in sorted({r[key] for r in records})}

    # Estabilidade: fração de exemplos com o mesmo resultado (passou/falhou) em todas as execuções.
    outcomes: dict[str, set] = {}
    for r in records:
        outcomes.setdefault(r["id"], set()).add(r["passed"])
    stable = sum(1 for v in outcomes.values() if len(v) == 1) / len(outcomes) if outcomes else None

    def mean_of(rs, key):
        vals = [r["style"][key] for r in rs if r.get("style", {}).get(key) is not None]
        return round(statistics.mean(vals), 3) if vals else None

    style_by_mode = {}
    for mode in sorted({r["mode"] for r in records}):
        rs = [r for r in records if r["mode"] == mode]
        style_by_mode[mode] = {f"{k}_{s}": mean_of(rs, f"{k}_{s}")
                               for k in STYLE_KEYS for s in ("in", "out")}
        style_by_mode[mode]["cliches_novos"] = mean_of(rs, "cliches_novos")

    return {
        "pass_rate": rate(records),
        "by_category": by("category"),
        "by_mode": by("mode"),
        "errors": sum(1 for r in records if r["error"]),
        "truncated": sum(1 for r in records if r["truncated"]),
        "avg_critical_alerts": round(statistics.mean(r["critical_alerts"] or 0 for r in records), 2),
        "latency_mean_s": round(statistics.mean(durations), 2) if durations else None,
        "latency_max_s": round(max(durations), 2) if durations else None,
        "stability": round(stable, 3) if stable is not None else None,
        "cliches_novos_por_ex": mean_of(records, "cliches_novos"),
        "style_by_mode": style_by_mode,
    }


def write_markdown(result: dict, path: Path) -> None:
    """Relatório para revisão humana: original x resultado, com espaço para notas."""
    m, s = result["meta"], result["summary"]
    lines = [
        f"# Avaliação — {m['model']} — prompt {m['prompt_version']}",
        "",
        f"- Data: {m['timestamp']} · execuções: {m['runs']} · VRAM: {m['vram_mb']} MB",
        f"- Aprovação nos critérios objetivos: **{s['pass_rate']:.0%}** · "
        f"latência média {s['latency_mean_s']} s · estabilidade {s['stability']}",
        "",
        "Revisão humana sugerida (1 a 5): **fidelidade** (mesmo significado e ressalvas), "
        "**fluência** (português natural e correto), **adequação ao modo**.",
        "",
        "## Estilo por modo (médias: original → resultado)",
        "",
        "| Modo | Variação das frases | Variedade de vocabulário | Voz passiva | Clichês | Clichês novos |",
        "|---|---|---|---|---|---|",
    ]
    for mode, st in s.get("style_by_mode", {}).items():
        cell = lambda k: f"{st[k + '_in']} → {st[k + '_out']}"  # noqa: E731
        lines.append(f"| {mode} | {cell('variacao_frases')} | {cell('variedade_vocabulario')} | "
                     f"{cell('voz_passiva')} | {cell('cliches')} | {st['cliches_novos']} |")
    lines.append("")
    for r in result["records"]:
        if r["run"] != 1:
            continue
        lines += [
            f"## {r['id']} · {r['mode']} · {'✅' if r['passed'] else '❌'}",
            "",
            f"**Original:** {r['input']}",
            "",
            f"**Resultado:** {r['output'] or '(erro: ' + str(r['error']) + ')'}",
            "",
        ]
        if r["failures"]:
            lines.append(f"**Falhas:** {'; '.join(r['failures'])}  ")
        if r.get("style"):
            st = r["style"]
            lines.append(f"**Estilo:** variação das frases {st['variacao_frases_in']} → "
                         f"{st['variacao_frases_out']} · vocabulário {st['variedade_vocabulario_in']} → "
                         f"{st['variedade_vocabulario_out']} · passiva {st['voz_passiva_in']} → "
                         f"{st['voz_passiva_out']} · clichês {st['cliches_in']} → {st['cliches_out']}  ")
        if r["alerts"]:
            lines.append(f"**Alertas do validador:** {'; '.join(r['alerts'])}  ")
        lines += ["**Nota humana:** fidelidade _ · fluência _ · modo _", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def compare(path_a: Path, path_b: Path) -> None:
    a = json.loads(path_a.read_text(encoding="utf-8"))
    b = json.loads(path_b.read_text(encoding="utf-8"))
    label = lambda r: f"{r['meta']['model']} / {r['meta']['prompt_version']}"  # noqa: E731
    print(f"{'métrica':<22} {'A: ' + label(a):<45} {'B: ' + label(b)}")
    for key in ["pass_rate", "avg_critical_alerts", "latency_mean_s", "latency_max_s",
                "stability", "errors", "truncated"]:
        print(f"{key:<22} {str(a['summary'][key]):<45} {b['summary'][key]}")
    print(f"{'vram_mb':<22} {str(a['meta']['vram_mb']):<45} {b['meta']['vram_mb']}")
    print("\nPor modo:")
    for mode in a["summary"]["by_mode"]:
        print(f"  {mode:<20} {str(a['summary']['by_mode'][mode]):<45} {b['summary']['by_mode'].get(mode)}")

    print("\nEstilo por modo (resultado; A → B):")
    for mode, sa in a["summary"].get("style_by_mode", {}).items():
        sb = b["summary"].get("style_by_mode", {}).get(mode, {})
        cells = [f"{k}: {sa.get(k + '_out')} → {sb.get(k + '_out')}" for k in STYLE_KEYS]
        print(f"  {mode:<12} " + " · ".join(cells) +
              f" · clichês novos: {sa.get('cliches_novos')} → {sb.get('cliches_novos')}")

    passed = lambda res: {r["id"] for r in res["records"] if r["run"] == 1 and r["passed"]}  # noqa: E731
    pa, pb = passed(a), passed(b)
    if pb - pa:
        print("\nPassaram só em B:", ", ".join(sorted(pb - pa)))
    if pa - pb:
        print("Passaram só em A:", ", ".join(sorted(pa - pb)))


def rescore(path: Path) -> Path:
    """Reaplica os critérios atuais de examples.json a resultados já gerados.

    Útil quando um critério é corrigido: evita rodar o modelo de novo e mantém
    a comparação entre versões justa (todas julgadas pelo mesmo gabarito).
    """
    result = json.loads(path.read_text(encoding="utf-8"))
    examples = {e["id"]: e for e in load_examples()}
    for r in result["records"]:
        if r["error"] or r["id"] not in examples:
            continue
        r["failures"] = check_example(examples[r["id"]], r["output"])
        r["passed"] = not r["failures"]
        report = validate(r["input"], r["output"], r["mode"])
        r["critical_alerts"], r["warnings"] = len(report.critical), len(report.warnings)
        r["alerts"] = [f"{i.severity}:{i.category}:{', '.join(i.items)}" for i in report.issues]
        r["style"] = style_metrics(r["input"], r["output"])
    result["summary"] = summarize(result["records"])
    result["meta"]["rescored_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(result, path.with_suffix(".md"))
    print(f"{path.name}: aprovação {result['summary']['pass_rate']:.0%}")
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="modelo do Ollama (padrão: config.py / HUMANIZA_MODEL)")
    parser.add_argument("--runs", type=int, default=1, help="execuções por exemplo (estabilidade)")
    parser.add_argument("--ids", nargs="*", help="rodar só estes exemplos")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("A.json", "B.json"))
    parser.add_argument("--rescore", nargs="+", type=Path, metavar="R.json",
                        help="reaplica os critérios atuais a resultados existentes")
    args = parser.parse_args()

    if args.compare:
        compare(*args.compare)
        return
    if args.rescore:
        for p in args.rescore:
            rescore(p)
        return

    settings = Settings.from_env()
    if args.model:
        settings = replace(settings, model=args.model)

    examples = load_examples(args.ids)
    print(f"Avaliando {len(examples)} exemplos × {args.runs} execução(ões) "
          f"com {settings.model} (prompt {PROMPT_VERSION})\n")
    start = time.perf_counter()
    result = run_evaluation(settings, examples, args.runs)
    result["meta"]["wall_time_s"] = round(time.perf_counter() - start, 1)

    RESULTS_DIR.mkdir(exist_ok=True)
    stem = f"{datetime.now():%Y%m%d-%H%M%S}_{re.sub(r'[^A-Za-z0-9._-]', '-', settings.model)}_{PROMPT_VERSION}"
    json_path = RESULTS_DIR / f"{stem}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(result, RESULTS_DIR / f"{stem}.md")

    s = result["summary"]
    print(f"\nAprovação: {s['pass_rate']:.0%} | latência média {s['latency_mean_s']}s | "
          f"alertas críticos/ex. {s['avg_critical_alerts']} | estabilidade {s['stability']} | "
          f"VRAM {result['meta']['vram_mb']} MB")
    print(f"Por modo: {s['by_mode']}")
    print(f"Clichês novos por exemplo: {s['cliches_novos_por_ex']}")
    print(f"Resultados: {json_path}")


if __name__ == "__main__":
    main()
