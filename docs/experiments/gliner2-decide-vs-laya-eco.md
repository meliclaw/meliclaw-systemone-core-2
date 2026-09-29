# Experimento: GLiNER2.5-multi-Decide vs laya no corpus real de ecocardiogramas

- **Status:** **executado e fechado em 2026-09-29. Resultado: NÃO integrar.**
  GLiNER2.5-multi-Decide perdeu de laya:multilingual nos 149 casos reais de
  eco: precisão 0.277 vs 0.494, acurácia 0.282 vs 0.718 (mesmo recall=1.000).
  Ver §"Resultado" no final deste documento. As correções de v1→v2 abaixo
  (modelo certo, arquitetura real) continuam válidas como registro do que foi
  corrigido no caminho.
- **Objetivo:** decidir se vale a pena integrar um modelo `GLiNER2.5` como
  família nova do Ollaya, comparando contra `laya:multilingual` **no mesmo
  corpus real** já usado na Fase 7 de `vetsync-diagnostic` — não no benchmark
  genérico do fornecedor, e não no modelo errado.
- **Não objetivo:** integrar no Rust do Ollaya. Isso só entra em pauta se o
  resultado do experimento justificar (ver "Critério de decisão").

## Correção 1 — o modelo certo é o multilíngue

Os laudos são PT-BR. `fastino/GLiNER2.5-Decide` (340M) é **só inglês** — a
própria ficha diz "The 340M English classification model". Modelo certo:
**`fastino/GLiNER2.5-multi-Decide`**.

Specs confirmadas via API do Hugging Face (2026-09-29), não o texto colado:

| | Valor confirmado | O que o texto colado dizia |
|---|---|---|
| Parâmetros | **287.4M** (`safetensors.parameters`) | 340M (esse é o modelo inglês) |
| Encoder | `deberta-v2`, hidden=768, 12 camadas (tamanho **base**) | "DeBERTa-v3-large" |
| Benchmark (`fast-decisions`, próprio fornecedor) | **56.7%** (GLiNER2.5-multi-Decide) | 60.2% (esse número é do modelo inglês) |
| Benchmark, Laya Router (mesma tabela) | 46.6% | 46.6% (esse batia) |

A vantagem real sobre "Laya Router" no benchmark do fornecedor é **+10.1pp**,
não +13.6pp — e ainda assim, benchmark genérico do fornecedor, não do nosso
domínio.

## Correção 2 — a arquitetura não é "encoder + MLP pequeno"

O `config.json` real do repo declara `"architecture": "BoundaryExtractor"`, com
um `boundary_head` de propose-then-rerank: candidatos, atenção de boundary
(2 camadas), top-k, cabeça de contagem, abstenção. **Não é** o padrão simples
"`[L]` marker + MLP de 4 tensores/2.1M params" que o pacote colado descrevia
para o modelo inglês — aquele texto descrevia (ou simplificava mal) uma coisa
mais simples do que o modelo real é.

Consequência prática: **exportar isso para ONNX à mão, copiando o padrão de
`nli` (DeBERTa-v3 + head simples), é um projeto de engenharia bem maior do que
se pensava** — precisa replicar propose-then-rerank, não só fundir um head.
Não vale começar por aí.

## Correção 3 — caminho oficial é mais barato: usar a lib, não exportar

O README oficial (`fastino-ai/GLiNER2`) é claro: **"CPU first: fast local
inference on standard hardware — no GPU required"**. Instalação:

```bash
pip install gliner2[local]
```

```python
from gliner2 import AutoExtractor
model = AutoExtractor.from_pretrained("fastino/GLiNER2.5-multi-Decide")
model.classify_text("<texto>", {"internacao": ["sim", "nao"]})
```

Isso já roda em CPU, no mesmo tipo de máquina do VPS de produção. **Não faz
sentido gastar semanas exportando para ONNX antes de saber se o modelo sequer
ganha do laya nos nossos dados.** O experimento troca de ordem: primeiro mede
com a lib oficial (barato), export/integração fica para depois, condicionado
ao resultado.

## Correção 4 — janela de contexto (confirmada em `docs/api.md`)

| Modelo | Janela | Encoder |
|---|---|---|
| `laya:en` | 512 tokens | ModernBERT-large (421M) |
| `laya:multilingual` (produção) | **1.024 tokens** | mmBERT-base (322M) |
| `GLiNER2.5-multi-Decide` | **512 tokens** | mDeBERTa-v2/v3-base (287M) |

laya:multilingual tem o dobro da janela do GLiNER2.5-multi-Decide. Isso já
mordeu a gente uma vez (Fase 7 original: laudo completo → 26% `STATE_TRUNCATED`
em laya, que tem MAIS contexto). Com GLiNER2.5 o risco de truncar seria maior
para textos longos.

**Mas não é risco neste experimento**: as `Conclusão` reais dos 149 casos têm
mediana 12 palavras, p95 42, máximo 49 (medido em 2026-09-29) — bem abaixo de
qualquer limite de 512 tokens. Enviar só a Conclusão (já é o plano) neutraliza
a diferença de janela para este corpus específico. Só reaparece como risco se
algum dia alguém mandar o laudo inteiro para o GLiNER2.5 em vez da Conclusão.

## Dados: o mesmo corpus, sem inventar nada novo

`dataset/vet/train/ecocardiografia/*.md` (repositório `agentic-platform`), os
mesmos 149 laudos com `qualidade_dado: ok` da Fase 7 de `vetsync-diagnostic`.
Ground truth idêntico: `risco == moderado` → esperado `internacao = true`.
Pasta `old/` sempre ignorada.

Números de referência do laya (já medidos, não repetir):

| Métrica | laya:multilingual (Conclusão apenas) |
|---|---|
| Recall | 1.000 |
| Precisão | 0.494 |
| Acurácia | 0.718 |
| Erros de chamada | 0/149 |

## Fases

### Fase 1 — Rodar GLiNER2.5-multi-Decide via lib oficial (CPU)

1. `pip install gliner2[local]` num venv isolado (Python 3.10+, exigido pelo
   pacote).
2. Carregar `fastino/GLiNER2.5-multi-Decide` via `AutoExtractor.from_pretrained`.
3. Reusar a mesma extração da Conclusão já validada em `vetsync-diagnostic`
   (mesmo texto de entrada dos dois modelos — comparação justa).
4. Para cada um dos 149 casos, chamar
   `model.classify_text(conclusao, {"internacao": ["sim", "nao"]})` (ou schema
   equivalente — confirmar a forma exata do schema de classificação binária na
   documentação da lib antes de rodar em lote).
5. Medir tempo de CPU por chamada (mesma métrica que falta para laya no VPS,
   então os dois números saem juntos, comparáveis).

**Saída:** `gliner2_resultado_conclusao.jsonl`, mesmo formato de
`fase7_resultado_conclusao.jsonl` (`numero`, `risco`, `esperado`, `previsto`,
`score`/`confidence`).

### Fase 2 — Calibração (o modelo não vem calibrado para nosso limiar)

1. Calcular ECE (*expected calibration error*) nos 149 casos.
2. Buscar o melhor limiar por busca em grade, com `recall = 1.0` **obrigatório**
   — mesma disciplina usada para laya na Fase 7 de `vetsync-diagnostic`
   (`best_safe`, não só melhor acurácia geral).

### Fase 3 — Comparação cabeça a cabeça

| Métrica | laya:multilingual | GLiNER2.5-multi-Decide |
|---|---|---|
| Recall (limiar com recall=1.0 obrigatório) | 1.000 | ? |
| Precisão nesse limiar | 0.494 | ? |
| Acurácia | 0.718 | ? |
| Latência CPU por chamada | ~1-2s e2e (medido em produção) | ? (medir na Fase 1) |
| Erros de execução | 0/149 | ? |

### Fase 4 (condicional) — Caminho de integração, só se valer a pena

Só entra em pauta se o critério de decisão abaixo passar. Nesse caso, a
pergunta muda de "vale a pena" para "como integrar" — e aí sim vira um projeto
de exportação/parity real (ONNX do `BoundaryExtractor`, ou manter como
processo Python separado tipo `openjev`, a decidir com dados na mão).

## Critério de decisão

Só vale seguir para a Fase 4 se, no mesmo corpus real:

1. Recall ≥ 1.000 (não pode perder nenhum caso que precisava internar).
2. Com esse recall, precisão **melhor** que 0.494.
3. Latência CPU aceitável para o VPS de produção (sem GPU — o README só
   garante "no GPU required", não garante latência aceitável para o caso de
   uso).

Se qualquer um falhar, o resultado fica documentado como achado, sem obrigação
de integrar.

## Fora de escopo deste experimento

- Exportar para ONNX ou integrar no Rust do Ollaya — condicional à Fase 4.
- Treinar/ajustar o GLiNER2.5 — só inferência do checkpoint público.
- Validação clínica do resultado por veterinário — mesma ressalva já registrada
  para laya (ASM-001/Q-003 em `vetsync-diagnostic`).

## Resultado (Fases 1-3 executadas, 2026-09-29)

Setup: `pip install "gliner2[local]" "transformers>=5" protobuf sentencepiece`
(venv isolado). `transformers` 4.x quebra o load do tokenizer (bug de
`extra_special_tokens`) — precisa 5.x, que é o que o `encoder_config` do
modelo já declarava.

| Métrica | laya:multilingual | GLiNER2.5-multi-Decide |
|---|---|---|
| Recall (limiar com recall=1.0 obrigatório) | 1.000 | 1.000 |
| Precisão nesse limiar | 0.494 | **0.277** |
| Acurácia | 0.718 | **0.282** |
| Latência CPU p50/p95 | ~1-2s e2e (medido em produção, via HTTP) | **129ms / 332ms** (in-process, sem rede) |
| Erros de execução | 0/149 | 0/149 |

Achado adicional: o `score_sim` (probabilidade de "sim"/internar) máximo entre
os 41 casos que realmente precisavam internar foi **0.493** — nunca cruza o
limiar padrão de 0.5 da própria lib. O modelo nunca está "confiante" em
recomendar internação, nem nos casos graves. A sobreposição entre os grupos
esperado-interna (mediana 0.350) e esperado-não-interna (mediana 0.274) é
maior, proporcionalmente, que a do laya.

Latência é o único eixo onde GLiNER2.5 ganha (bem — ~10x mais rápido, e
in-process, sem round-trip HTTP), mas não compensa perder tanto em precisão e
acurácia numa decisão clínica.

### Critério de decisão — avaliado

1. Recall ≥ 1.000 — ✅ passa.
2. Precisão melhor que 0.494 — ❌ **falha** (0.277).
3. Latência aceitável — ✅ passa (é a única vantagem).

**Falhou o critério 2. Não avança para a Fase 4. GLiNER2.5-multi-Decide não é
integrado ao Ollaya nem ao vetsync-diagnostic.**

Evidência: `evidencia_gliner2_resultado_eco.jsonl` (149 linhas, uma por caso),
script `convert/ollaya_convert/families/gliner2/eval_exp001_eco.py`.
