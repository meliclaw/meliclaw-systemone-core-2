#!/usr/bin/env python3
"""Deriva uma seção "Conclusão" para laudos de ultrassonografia que não têm
nenhuma (0/254, verificado) — a partir dos campos JÁ estruturados no
frontmatter (`diagnosticos`, `<orgao>_achado`, flags `alterado`), sem inventar
texto clínico novo. Ver docs/experiments/decision-models-laudos-veterinarios.md
§2.2 (EXP-002).

Uso:
    python3 derive_conclusao_ultrasom.py --dry-run   # mostra 3 exemplos, nao escreve
    python3 derive_conclusao_ultrasom.py --apply      # escreve nos 254 arquivos
"""
import argparse
import re
from pathlib import Path

DS = Path("/Volumes/Backup/Projects/src/heyzify/agentic-platform/dataset/vet/train/ultrassonografia")

ORGAO_LABEL = {
    "figado": "fígado",
    "vesicula_biliar": "vesícula biliar",
    "baco": "baço",
    "estomago": "estômago",
    "intestinos": "alças intestinais",
    "rins": "rins",
    "ureteres": "ureteres",
    "adrenais": "adrenais",
    "vesicula_urinaria": "vesícula urinária",
    "pancreas": "pâncreas",
}

DIAG_TO_ORGAOS = {
    "achado_hepatico": ["figado"],
    "achado_renal": ["rins"],
    "achado_vesical": ["vesicula_urinaria"],
    "achado_pancreatico": ["pancreas"],
}


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.groups()
    fm = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, body


def derivar_conclusao(fm: dict) -> str:
    """Deriva só do CÓDIGO de diagnóstico + nome do órgão — nunca do texto
    livre `<orgao>_achado`, que já vem truncado na fonte (corta a meio de
    palavra, ver REL-20260407-018.md) e produziria uma frase falsamente
    completa se citada como se fosse a conclusão real."""
    diagnosticos_raw = fm.get("diagnosticos", "[]").strip("[]")
    diagnosticos = [d.strip() for d in diagnosticos_raw.split(",") if d.strip()]

    if diagnosticos == ["exame_abdominal_sem_alteracoes"]:
        return "Exame abdominal sem alterações."

    organs_ja_citados = []
    for diag in diagnosticos:
        for organ in DIAG_TO_ORGAOS.get(diag, []):
            if organ not in organs_ja_citados:
                organs_ja_citados.append(organ)

    if not organs_ja_citados:
        # diagnostico presente mas sem organo mapeado — fallback honesto
        return "Achado(s): " + ", ".join(diagnosticos).replace("_", " ") + "."

    labels = [ORGAO_LABEL.get(o, o) for o in organs_ja_citados]
    if len(labels) == 1:
        return f"Achado em {labels[0]}. Ver seção correspondente no corpo do laudo para detalhes."
    return f"Achados em {', '.join(labels[:-1])} e {labels[-1]}. Ver seções correspondentes no corpo do laudo para detalhes."


def process(path: Path):
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if re.search(r"Conclus[aã]o", body):
        return None  # já tem, não mexe
    conclusao = derivar_conclusao(fm)
    return conclusao


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    files = sorted(DS.glob("*.md"))  # old/ é subpasta, glob não desce
    if args.dry_run or not args.apply:
        for f in files[:3]:
            print(f"=== {f.name} ===")
            print(process(f))
            print()
        # mais 2 exemplos com achado real, nao so o caso normal
        exemplos_achado = [f for f in files if "alterado" in f.read_text(encoding="utf-8")][:2]
        for f in exemplos_achado:
            print(f"=== {f.name} (com achado) ===")
            print(process(f))
            print()
        return

    alterados = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
        if not m:
            print(f"AVISO: {f.name} sem frontmatter reconhecível, pulado")
            continue
        fm_text, body = m.groups()
        fm, _ = parse_frontmatter(text)
        if re.search(r"Conclus[aã]o", body):
            continue
        conclusao = derivar_conclusao(fm)
        novo_body = body.rstrip() + f"\n\nConclusão\n\n{conclusao}\n"
        novo_fm_text = fm_text.rstrip("\n") + "\nconclusao_origem: derivada_de_campos_estruturados"
        novo_texto = f"---\n{novo_fm_text}\n---\n{novo_body}"
        f.write_text(novo_texto, encoding="utf-8")
        alterados += 1
    print(f"{alterados} arquivos atualizados.")


if __name__ == "__main__":
    main()
