#!/usr/bin/env python3
"""Validação offline do openjev-latest (api.codiv.ai) com o PAYLOAD REAL de produção
do vetsync-diagnostic: `state` objeto {numero_relatorio, laudo} e as 3 perguntas
(internacao noul, gravidade score, causa_provavel choice) — os experimentos
anteriores usaram `state` string e só `gravidade`.

Uso:
  export CODIV_API_KEY=...            # nunca commitar / colar em chat
  python3 eval_codiv_eco_prod_payload.py --probe     # 1 chamada: confirma que noul/choice funcionam
  python3 eval_codiv_eco_prod_payload.py             # corrida completa (149 casos, ~25 min, rate limit 10s)
  python3 eval_codiv_eco_prod_payload.py --analyze   # só análise do jsonl já gravado (não chama a API)

Grava incrementalmente (append) e retoma de onde parou. Cliente HTTP = curl: urllib
tomou 403 persistente no codiv.ai (ver resultado-final-decision-models.pt.md §4.2).
O jsonl guarda só número do laudo, rótulo e respostas do modelo — nenhum texto clínico.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

CODIV_URL = "https://api.codiv.ai/v1/systemone"
MODEL = "openjev-latest"
HERE = Path(__file__).resolve().parent
DS = Path(os.environ.get("DATASET_ECO", "/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train/ecocardiografia"))
OUT = HERE / "evidencia_codiv_eco_149_prod_payload.jsonl"
SLEEP_S = 10  # rate limit observado no codiv.ai

# Idênticas às de vetsync-diagnostic/src/laya.rs (questions_for(Full)).
QUESTIONS = {
    "internacao": {"type": "noul", "instructions": "This echocardiogram report shows findings severe enough to require clinical hospitalization of the patient"},
    "gravidade": {"type": "score", "instructions": "Overall clinical severity of the findings in this echocardiogram",
                  "criteria": ["Normal or discreet finding, no follow-up urgency",
                               "Moderate finding, needs monitoring/treatment",
                               "Severe finding, needs immediate clinical action"]},
    "causa_provavel": {"type": "choice", "instructions": "Most likely underlying cause driving the report's conclusion",
                       "criteria": {
                           "disfuncao_diastolica": "Diastolic dysfunction (relaxation/restrictive pattern)",
                           "disfuncao_sistolica": "Systolic dysfunction of left or right ventricle",
                           "insuficiencia_valvar": "Valve insufficiency/regurgitation (mitral, tricuspid, aortic, pulmonary)",
                           "normal": "No relevant structural or functional abnormality",
                           "outro": "Other or inconclusive finding"}},
}
CAUSAS = set(QUESTIONS["causa_provavel"]["criteria"])


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, m.group(2)


def casos_elegiveis():
    casos = []
    for f in sorted(DS.glob("*.md")):
        fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if fm.get("qualidade_dado") != "ok" or fm.get("risco") not in ("baixo", "baixo_moderado", "moderado"):
            continue
        m = re.search(r"Conclus[aã]o\s*\n+(.*)", body, re.DOTALL)
        if not m or not m.group(1).strip():
            continue
        casos.append((fm.get("numero_relatorio", f.stem), fm["risco"], m.group(1).strip()))
    return casos


def chamar(numero, conclusao, key):
    body = json.dumps({"model": MODEL, "state": {"numero_relatorio": numero, "laudo": conclusao}, "questions": QUESTIONS})
    out = subprocess.run(
        ["curl", "-s", "--max-time", "45", "-w", "\n%{http_code}", "-X", "POST", CODIV_URL,
         "-H", f"Authorization: Bearer {key}", "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, text=True, check=True,
    ).stdout
    corpo, _, status = out.rpartition("\n")
    return int(status or 0), corpo


def extrair(status, corpo):
    """Devolve (respostas normalizadas, erro). Não inventa campo que não veio."""
    try:
        r = json.loads(corpo)
    except json.JSONDecodeError:
        return None, f"http={status} corpo não-JSON"
    if status != 200 or "answers" not in r:
        return None, f"http={status} {json.dumps(r)[:300]}"
    a = r["answers"]
    row = {"model": r.get("model"), "tokens_in": (r.get("usage") or {}).get("input_tokens")}
    row["gravidade"] = (a.get("gravidade") or {}).get("score")
    row["internacao_noul"] = (a.get("internacao") or {}).get("noul")
    ch = a.get("causa_provavel") or {}
    row["causa"], row["causa_conf"] = ch.get("choice"), ch.get("confidence")
    faltando = [k for k in ("gravidade", "internacao_noul", "causa") if row[k] is None]
    return row, (f"faltou {faltando}" if faltando else None)


def probe(key):
    numero, risco, conclusao = casos_elegiveis()[0]
    status, corpo = chamar(numero, conclusao, key)
    row, erro = extrair(status, corpo)
    print(f"http={status} risco={risco}")
    print(json.dumps(row, ensure_ascii=False) if row else corpo[:500])
    if erro or (row and row["causa"] not in CAUSAS):
        print(f"\nPROBE FALHOU: {erro or 'causa fora das 5 categorias: ' + str(row['causa'])}")
        sys.exit(2)
    print("\nPROBE OK: noul, score e choice aceitos com o payload de produção.")


def correr(key):
    casos = casos_elegiveis()
    feitos = set()
    if OUT.exists():
        feitos = {json.loads(l)["numero"] for l in OUT.read_text().splitlines() if l.strip()}
    print(f"casos elegíveis: {len(casos)} | já feitos: {len(feitos)}", file=sys.stderr)
    with OUT.open("a") as fout:
        for i, (numero, risco, conclusao) in enumerate(casos):
            if numero in feitos:
                continue
            row = {"numero": numero, "risco": risco, "esperado": risco == "moderado"}
            for tentativa in range(3):
                try:
                    status, corpo = chamar(numero, conclusao, key)
                except Exception as e:  # curl falhou/timeout
                    status, corpo = 0, str(e)
                dados, erro = extrair(status, corpo)
                if status in (429, 503) and tentativa < 2:
                    time.sleep(SLEEP_S * (tentativa + 2))
                    continue
                break
            row.update(dados or {})
            row["erro"] = erro
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            if (i + 1) % 10 == 0:
                print(f"[{i+1}/{len(casos)}] {numero} grav={row.get('gravidade')} causa={row.get('causa')} erro={erro}", file=sys.stderr)
            time.sleep(SLEEP_S)


def metricas(rows, corte):
    tp = sum(1 for r in rows if r["esperado"] and r["gravidade"] >= corte)
    fn = sum(1 for r in rows if r["esperado"] and r["gravidade"] < corte)
    fp = sum(1 for r in rows if not r["esperado"] and r["gravidade"] >= corte)
    tn = sum(1 for r in rows if not r["esperado"] and r["gravidade"] < corte)
    rec = tp / (tp + fn) if tp + fn else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    return tp, fn, fp, tn, rec, prec, (tp + tn) / len(rows)


def analisar():
    todos = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()]
    rows = [r for r in todos if r.get("gravidade") is not None]
    erros = [r for r in todos if r.get("erro")]
    print(f"linhas: {len(todos)} | com gravidade: {len(rows)} | com erro/campo faltando: {len(erros)}")
    for r in erros[:5]:
        print("  erro:", r["numero"], r["erro"])
    if not rows:
        return
    pos = [r["gravidade"] for r in rows if r["esperado"]]
    neg = [r["gravidade"] for r in rows if not r["esperado"]]
    print(f"\nn={len(rows)} positivos(moderado)={len(pos)} negativos={len(neg)}")
    for nome, xs in (("positivos", pos), ("negativos", neg)):
        print(f"  {nome}: min={min(xs):.3f} mediana={statistics.median(xs):.3f} max={max(xs):.3f}")

    # Regra ASM-001: recall = 1.0 obrigatório -> alert_min = menor score entre os positivos.
    alert = round(min(pos) - 0.0005, 3)
    print(f"\n== alert_min (regra ASM-001: recall=1.0) = {alert}")
    tp, fn, fp, tn, rec, prec, acc = metricas(rows, alert)
    print(f"   TP={tp} FN={fn} FP={fp} TN={tn} recall={rec:.3f} precisão={prec:.3f} acurácia={acc:.3f}")
    print("   (referência laya:multilingual: recall 1.000 / precisão 0.494 / acurácia 0.718 — mesmos 149 casos)")

    print("\n== varredura de cortes (positivo = risco 'moderado')")
    print("   corte  recall  precisão  acurácia   FP   FN")
    melhor = None
    for c in [x / 20 for x in range(2, 40)]:
        tp, fn, fp, tn, rec, prec, acc = metricas(rows, c)
        print(f"   {c:5.2f}  {rec:6.3f}  {prec:8.3f}  {acc:8.3f}  {fp:4d} {fn:4d}")
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        if melhor is None or f1 > melhor[0]:
            melhor = (f1, c, rec, prec)
    print(f"   -> melhor F1 = {melhor[0]:.3f} em corte {melhor[1]:.2f} (recall {melhor[2]:.3f}, precisão {melhor[3]:.3f})")
    print("   hospitalization_min é decisão clínica: sugestão = corte de melhor F1 acima, a validar com veterinário.")

    hosp = melhor[1] if melhor[1] > alert else round(alert + 0.4, 2)
    print(f"\n== risco real x banda (alert_min={alert}, hospitalization_min={hosp})")
    def banda(g):
        return "internacao" if g >= hosp else ("monitorar" if g >= alert else "sem_alerta")
    cnt = Counter((r["risco"], banda(r["gravidade"])) for r in rows)
    for risco in ("baixo", "baixo_moderado", "moderado"):
        print(f"   {risco:15s} " + "  ".join(f"{b}={cnt[(risco, b)]}" for b in ("sem_alerta", "monitorar", "internacao")))

    print("\n== causa_provavel (choice) e internacao (noul)")
    comcausa = [r for r in rows if r.get("causa")]
    print(f"   respondeu causa: {len(comcausa)}/{len(rows)} | fora das 5 categorias: {sum(1 for r in comcausa if r['causa'] not in CAUSAS)}")
    print("   distribuição:", dict(Counter(r["causa"] for r in comcausa)))
    confs = [r["causa_conf"] for r in comcausa if r.get("causa_conf") is not None]
    if confs:
        print(f"   confiança: min={min(confs):.2f} mediana={statistics.median(confs):.2f} max={max(confs):.2f} | <0.40: {sum(1 for c in confs if c < 0.4)}")
    nou = [r["internacao_noul"] for r in rows if r.get("internacao_noul") is not None]
    if nou:
        print(f"   noul: min={min(nou):.4f} mediana={statistics.median(nou):.4f} max={max(nou):.4f} (Laya era 0.0009–0.058, sem discriminar)")
        npos = [r["internacao_noul"] for r in rows if r["esperado"] and r.get("internacao_noul") is not None]
        nneg = [r["internacao_noul"] for r in rows if not r["esperado"] and r.get("internacao_noul") is not None]
        if npos and nneg:
            print(f"   noul positivos mediana={statistics.median(npos):.4f} | negativos mediana={statistics.median(nneg):.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()
    if args.analyze:
        return analisar()
    key = os.environ.get("CODIV_API_KEY")
    if not key:
        sys.exit("defina CODIV_API_KEY no ambiente (não passe a key por argumento nem commite)")
    if args.probe:
        return probe(key)
    correr(key)
    analisar()


if __name__ == "__main__":
    main()
