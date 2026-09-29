#!/usr/bin/env python3
"""EXP-004 — few-shot real via laya nativo (paquete `laya`, mesmo checkpoint
laya-multilingual de produção). 2 exemplos fixos (retirados do pool de
avaliação) prependidos ao `laudo` real, mesmo formato de state do Rust
(dict numero_relatorio+laudo)."""
import json
import re
import time
from pathlib import Path

import laya

DS = Path("/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train/ecocardiografia")

EXEMPLO_NORMAL = ("REL-20260408-004", "Valvopatia mixomatosa mitral.\nInsuficiência valvar mitral de grau discreto sem remodelamento de câmaras cardíacas esquerdas.\n\nDisfunção diastólica ventricular esquerda de grau discreto.")
EXEMPLO_GRAVE = ("REL-20260410-011", "Valvopatia mixomatosa mitral.\nInsuficiência valvar mitral de grau importante com remodelamento de câmaras cardíacas esquerdas.\nPadrão restritivo de enchimento ventricular esquerdo.")
EXCLUIR = {EXEMPLO_NORMAL[0], EXEMPLO_GRAVE[0]}

QUESTIONS = {
    "gravidade": {"type": "score", "instructions": "Overall clinical severity of the findings in this echocardiogram",
                  "criteria": ["Normal or discreet finding, no follow-up urgency",
                               "Moderate finding, needs monitoring/treatment",
                               "Severe finding, needs immediate clinical action"]},
}

FEWSHOT_PREFIX = (
    f"Exemplo 1 (achado normal/discreto, gravidade baixa): {EXEMPLO_NORMAL[1]}\n\n"
    f"Exemplo 2 (achado importante, gravidade alta): {EXEMPLO_GRAVE[1]}\n\n"
    "Novo laudo a avaliar:\n"
)


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
    casos = []
    for f in sorted(DS.glob("*.md")):
        fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if fm.get("qualidade_dado") != "ok":
            continue
        numero = fm.get("numero_relatorio", f.stem)
        if numero in EXCLUIR:
            continue
        risco = fm.get("risco")
        if risco not in ("baixo", "baixo_moderado", "moderado"):
            continue
        esperado = risco == "moderado"
        m = re.search(r"Conclus[aã]o\s*\n+(.*)", body, re.DOTALL)
        if not m or not m.group(1).strip():
            continue
        casos.append((numero, risco, esperado, m.group(1).strip()))

    print(f"casos (excluindo os 2 few-shot): {len(casos)}")

    agent = laya.load("convaiinnovations/laya-multilingual", device="cpu")

    linhas_zero, linhas_few = [], []
    for i, (numero, risco, esperado, conclusao) in enumerate(casos):
        # zero-shot, mesmo formato do Rust em produção
        state_zero = {"numero_relatorio": numero, "laudo": conclusao}
        r0 = agent.system_one(state_zero, QUESTIONS)
        g0 = r0["answers"]["gravidade"]["score"]
        linhas_zero.append({"numero": numero, "risco": risco, "esperado": esperado, "gravidade": g0})

        # few-shot: mesmo formato, laudo prefixado com os 2 exemplos
        state_few = {"numero_relatorio": numero, "laudo": FEWSHOT_PREFIX + conclusao}
        r1 = agent.system_one(state_few, QUESTIONS)
        g1 = r1["answers"]["gravidade"]["score"]
        linhas_few.append({"numero": numero, "risco": risco, "esperado": esperado, "gravidade": g1})

        if (i + 1) % 20 == 0:
            print(f"[{i+1}/{len(casos)}]")

    out_dir = Path(__file__).parent
    with (out_dir / "resultado_zeroshot_producao_fmt.jsonl").open("w") as f:
        for l in linhas_zero:
            f.write(json.dumps(l) + "\n")
    with (out_dir / "resultado_fewshot.jsonl").open("w") as f:
        for l in linhas_few:
            f.write(json.dumps(l) + "\n")
    print("gravado.")


if __name__ == "__main__":
    main()
