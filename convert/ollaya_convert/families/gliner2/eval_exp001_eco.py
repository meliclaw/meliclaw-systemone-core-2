#!/usr/bin/env python3
"""EXP-001 — GLiNER2.5-multi-Decide contra os mesmos 149 casos reais de eco."""
import json
import re
import sys
import time
from pathlib import Path

from gliner2 import AutoExtractor

DS = Path("/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train/ecocardiografia")


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
        if risco not in ("baixo", "baixo_moderado", "moderado"):
            continue
        esperado = risco == "moderado"
        m = re.search(r"Conclus[aã]o\s*\n+(.*)", body, re.DOTALL)
        if not m or not m.group(1).strip():
            continue
        casos.append((fm.get("numero_relatorio", f.stem), risco, esperado, m.group(1).strip()))

    print(f"casos elegíveis: {len(casos)}", file=sys.stderr)

    t0 = time.time()
    model = AutoExtractor.from_pretrained("fastino/GLiNER2.5-multi-Decide")
    print(f"load: {time.time()-t0:.1f}s", file=sys.stderr)

    linhas = []
    tempos = []
    for i, (numero, risco, esperado, conclusao) in enumerate(casos):
        t0 = time.time()
        r = model.classify_text(conclusao, {"internacao": ["sim", "nao"]}, include_confidence=True)
        dt = time.time() - t0
        tempos.append(dt)
        label = r["internacao"]["label"]
        conf = r["internacao"]["confidence"]
        # score_sim: probabilidade de "sim" (internar), invertendo quando o label escolhido é "nao"
        score_sim = conf if label == "sim" else (1.0 - conf)
        linhas.append({"numero": numero, "risco": risco, "esperado": esperado, "label": label, "conf": conf, "score_sim": score_sim})
        if (i + 1) % 20 == 0:
            print(f"[{i+1}/{len(casos)}]", file=sys.stderr)

    out = Path(__file__).parent / "gliner2_resultado_eco.jsonl"
    with out.open("w") as f:
        for l in linhas:
            f.write(json.dumps(l) + "\n")

    tempos.sort()
    n = len(tempos)
    print(f"\nlatência CPU: p50={tempos[n//2]*1000:.0f}ms p95={tempos[int(n*0.95)]*1000:.0f}ms")
    print(f"resultado: {out}")


if __name__ == "__main__":
    main()
