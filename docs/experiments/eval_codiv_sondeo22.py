#!/usr/bin/env python3
"""Sondeo completo (22 casos: 11 eco + 11 ultrassonografia) contra
openjev-latest y jevk5-0.2 (codiv.ai) + laya:multilingual local (via servidor
real vetsync-diagnostic). Sin busqueda de umbral (n=22, ver plan doc)."""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

API_KEY = os.environ["TYPESAFE_API_KEY"]
CODIV_URL = "https://api.codiv.ai/v1/systemone"
LOCAL_URL = "http://localhost:8090/v1/diagnostico/eco"

ECO = [
    ("REL-20260408-004", "baixo"), ("REL-20260408-005", "baixo_moderado"),
    ("REL-20260408-007", "baixo"), ("REL-20260409-002", "baixo"),
    ("REL-20260409-003", "baixo"), ("REL-20260410-001", "baixo"),
    ("REL-20260408-008", "moderado"), ("REL-20260409-005", "moderado"),
    ("REL-20260410-011", "moderado"), ("REL-20260421-002", "moderado"),
    ("REL-20260429-006", "moderado"),
]
ULTRASSOM = [
    ("REL-20260406-002", "baixo"), ("REL-20260406-004", "baixo"),
    ("REL-20260406-005", "baixo"), ("REL-20260406-006", "baixo"),
    ("REL-20260406-007", "baixo"), ("REL-20260407-001", "baixo"),
    ("REL-20260406-003", "moderado"), ("REL-20260407-009", "moderado"),
    ("REL-20260407-017", "moderado"), ("REL-20260407-018", "moderado"),
    ("REL-20260409-001", "moderado"),
]

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


def carregar_conclusao(categoria_dir, numero):
    for f in categoria_dir.glob(f"{numero}.md"):
        text = f.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        m = re.search(r"Conclus[aã]o\s*\n+(.*)", body, re.DOTALL)
        return m.group(1).strip() if m else None
    return None


def chamar_codiv(model, texto):
    import subprocess
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
    DATASET = Path("/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train")
    linhas = []
    todos = [("eco", DATASET / "ecocardiografia", ECO), ("ultrassom", DATASET / "ultrassonografia", ULTRASSOM)]

    for categoria, dir_path, lista in todos:
        for numero, risco in lista:
            conclusao = carregar_conclusao(dir_path, numero)
            if not conclusao:
                print(f"AVISO: sem conclusão para {numero}", file=sys.stderr)
                continue
            esperado = risco == "moderado"
            row = {"categoria": categoria, "numero": numero, "risco": risco, "esperado": esperado}
            for nome, fn in [
                ("laya_local", lambda: chamar_laya_local(numero, conclusao)),
                ("openjev_latest", lambda: chamar_codiv("openjev-latest", conclusao)),
                ("jevk5_0_2", lambda: chamar_codiv("jevk5-0.2", conclusao)),
            ]:
                try:
                    row[nome] = fn()
                except Exception as e:
                    row[nome] = None
                    print(f"ERRO {nome} {numero}: {e}", file=sys.stderr)
                if nome != "laya_local":
                    time.sleep(10)  # rate limit real do codiv.ai: confirmado que 1.5-3s falha, 10s funciona
            linhas.append(row)
            print(f"{categoria} {numero} risco={risco} laya={row.get('laya_local')} openjev={row.get('openjev_latest')} jevk5={row.get('jevk5_0_2')}")

    out = Path("/private/tmp/claude-501/-Volumes-Backup-Projects-src-heyzify-agentic-platform-meliclaw-decision-core/6b91825b-da49-44a5-b8df-75e9e9aa6e53/scratchpad/codiv_sondeo22_resultado.jsonl")
    with out.open("w") as f:
        for l in linhas:
            f.write(json.dumps(l) + "\n")
    print(f"\ngravado: {out}")


if __name__ == "__main__":
    main()
