#!/usr/bin/env python3
"""Escalado do sondeio codiv.ai (openjev-latest, jevk5-0.2) para os 236
casos de ultrassonografia com qualidade_dado:ok — confirma ou refuta o
achado de separação perfeita visto no sondeio de 11 casos. Grava
incrementalmente (append) para não perder progresso em caso de falha
parcial numa corrida de ~79 min."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

API_KEY = os.environ["TYPESAFE_API_KEY"]
CODIV_URL = "https://api.codiv.ai/v1/systemone"
LOCAL_URL = "http://localhost:8090/v1/diagnostico/eco"
DS = Path("/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train/ultrassonografia")
OUT = Path("/private/tmp/claude-501/-Volumes-Backup-Projects-src-heyzify-agentic-platform-meliclaw-decision-core/6b91825b-da49-44a5-b8df-75e9e9aa6e53/scratchpad/codiv_ultrasom_escala_resultado.jsonl")

QUESTIONS = {
    "gravidade": {"type": "score", "instructions": "Overall clinical severity of the findings in this veterinary report",
                  "criteria": ["Normal or discreet finding, no follow-up urgency",
                               "Moderate finding, needs monitoring/treatment",
                               "Severe finding, needs immediate clinical action"]},
}


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


def chamar_codiv(model, texto):
    body = json.dumps({"model": model, "state": texto, "questions": QUESTIONS})
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-X", "POST", CODIV_URL,
         "-H", f"Authorization: Bearer {API_KEY}", "-H", "Content-Type: application/json",
         "-d", body],
        capture_output=True, text=True, check=True,
    )
    r = json.loads(out.stdout)
    if "answers" not in r:
        raise RuntimeError(f"resposta sem answers: {r}")
    return r["answers"]["gravidade"]["score"]


def chamar_laya_local(numero, texto):
    body = json.dumps({"numero_relatorio": numero, "laudo_texto": texto}).encode("utf-8")
    req = urllib.request.Request(LOCAL_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        r = json.loads(resp.read())
    return r["data"]["gravidade"]


def main():
    ja_processados = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                ja_processados.add(json.loads(line)["numero"])
        print(f"retomando: {len(ja_processados)} já processados", file=sys.stderr)

    casos = []
    for f in sorted(DS.glob("*.md")):
        fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if fm.get("qualidade_dado") != "ok":
            continue
        risco = fm.get("risco")
        if risco not in ("baixo", "moderado"):
            continue
        numero = fm.get("numero_relatorio", f.stem)
        m = re.search(r"Conclus[aã]o\s*\n+(.*)", body, re.DOTALL)
        if not m or not m.group(1).strip():
            continue
        casos.append((numero, risco, m.group(1).strip()))

    print(f"casos elegíveis: {len(casos)}", file=sys.stderr)

    with OUT.open("a") as fout:
        for i, (numero, risco, conclusao) in enumerate(casos):
            if numero in ja_processados:
                continue
            esperado = risco == "moderado"
            row = {"numero": numero, "risco": risco, "esperado": esperado}
            try:
                row["laya_local"] = chamar_laya_local(numero, conclusao)
            except Exception as e:
                row["laya_local"] = None
                print(f"ERRO laya {numero}: {e}", file=sys.stderr)
            for nome, model in [("openjev_latest", "openjev-latest"), ("jevk5_0_2", "jevk5-0.2")]:
                try:
                    row[nome] = chamar_codiv(model, conclusao)
                except Exception as e:
                    row[nome] = None
                    print(f"ERRO {nome} {numero}: {e}", file=sys.stderr)
                time.sleep(10)
            fout.write(json.dumps(row) + "\n")
            fout.flush()
            if (i + 1) % 10 == 0:
                print(f"[{i+1}/{len(casos)}] {numero} laya={row.get('laya_local')} openjev={row.get('openjev_latest')} jevk5={row.get('jevk5_0_2')}", file=sys.stderr)

    print(f"\nconcluído: {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
