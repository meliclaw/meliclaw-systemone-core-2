#!/usr/bin/env python3
"""EXP-002b — laya real (servidor vetsync-diagnostic, /v1/diagnostico/eco)
contra os 254 laudos de ultrassonografia com Conclusão DERIVADA (§6 do doc
técnico). Ground truth: risco==moderado -> internacao esperada True.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

DS = Path("/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train/ultrassonografia")
API = "http://localhost:8090/v1/diagnostico/eco"


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.groups()
    fm = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip().strip('"')
    return fm, body


def main():
    files = sorted(DS.glob("*.md"))
    casos = []
    for f in files:
        fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if fm.get("qualidade_dado") != "ok":
            continue
        risco = fm.get("risco")
        if risco not in ("baixo", "moderado"):
            continue
        esperado = risco == "moderado"
        m = re.search(r"Conclus[aã]o\s*\n+(.*)", body, re.DOTALL)
        if not m or not m.group(1).strip():
            continue
        casos.append((fm.get("numero_relatorio", f.stem), risco, esperado, m.group(1).strip()))

    print(f"casos elegíveis: {len(casos)}", file=sys.stderr)

    tp = tn = fp = fn = 0
    erros = 0
    linhas = []
    for i, (numero, risco, esperado, conclusao) in enumerate(casos):
        body = json.dumps({"numero_relatorio": numero, "laudo_texto": conclusao}).encode("utf-8")
        req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                r = json.loads(resp.read())
        except Exception as e:
            erros += 1
            print(f"[{i+1}/{len(casos)}] {numero} ERRO {e}", file=sys.stderr)
            continue
        if r.get("status") != "ok":
            erros += 1
            print(f"[{i+1}/{len(casos)}] {numero} API-ERRO {r.get('error')}", file=sys.stderr)
            continue
        previsto = r["data"]["internacao"]
        gravidade = r["data"]["gravidade"]
        if esperado and previsto:
            tp += 1
        elif not esperado and not previsto:
            tn += 1
        elif not esperado and previsto:
            fp += 1
        else:
            fn += 1
        linhas.append({"numero": numero, "risco": risco, "esperado": esperado, "previsto": previsto, "gravidade": gravidade})
        if (i + 1) % 40 == 0:
            print(f"[{i+1}/{len(casos)}]", file=sys.stderr)

    total = tp + tn + fp + fn
    acc = (tp + tn) / total if total else 0
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")

    print("\n=== Matriz de confusão (internação: risco==moderado é positivo) ===")
    print(f"TP={tp}  FN={fn}")
    print(f"FP={fp}  TN={tn}")
    print(f"erros: {erros}")
    print(f"acurácia: {acc:.3f}  precisão: {prec:.3f}  recall: {rec:.3f}  total avaliado: {total}")

    out = Path("/private/tmp/claude-501/-Volumes-Backup-Projects-src-heyzify-agentic-platform-meliclaw-decision-core/6b91825b-da49-44a5-b8df-75e9e9aa6e53/scratchpad/exp002b_resultado.jsonl")
    with out.open("w") as f:
        for l in linhas:
            f.write(json.dumps(l) + "\n")
    print(f"\ndetalhe: {out}")


if __name__ == "__main__":
    main()
