# Plano: experimentos multi-modelo via API do codiv.ai

- **Estado:** sondeio inicial executado, sondeio completo (22 casos) pendente.
- **Objetivo:** sondar rápido (22 casos, não o corpus completo) se algum
  modelo servido pelo codiv.ai (OpenJev, Laya, Verdict, CLM, JevK5) discrimina
  melhor que o laya local (Ollaya) já medido nas Fases 1-4.
- **Relacionado:** `decision-models-laudos-veterinarios.pt.md` (métricas já
  medidas), `gliner2-decide-vs-laya-eco.md`.

## Segurança — antes de tocar código

O usuário colou uma API key real no chat (`sk-codiv-...`). **Recomenda-se
rotacioná-la** antes de usar em qualquer script — ficou exposta no histórico
desta sessão. Quando for usada:

- Nunca hardcoded no código nem commitada — só `export TYPESAFE_API_KEY=...`
  no shell, ou `.env` local (gitignored, igual a `vetsync-diagnostic/.env`).
- Nunca logada (nem no stdout de scripts de eval, nem em jsonl de evidência).

## Modelos a testar (5, via `typesafe-sdk` / `POST /v1/systemone`)

Os 5 nomes batem exatamente com os backends documentados em
`meliclaw-systemone-core/openjev/encoders.py` (docstring) — codiv.ai parece
ser um hosting gerenciado desse mesmo stack, não modelos novos:

| Modelo | Backend real (segundo encoders.py) | Checkpoint / arquitetura |
|---|---|---|
| `openjev-latest` (ou similar) | vLLM + DiffusionGemma (generativo, o mais pesado) | modelo grande, não encoder |
| Laya 1.0 | `laya-1.0`, pacote `laya` | ModernBERT-large/mmBERT-base — **mesmo que já medimos local** |
| Verdict 1.4 | `verdict-1.4` | ModernBERT-base + GLiClass, 151M, `heman10x/rlcd-modernbert-151m` |
| CLM 0.1 | `clm-v0.1` | Qwen3-8B embeddings + heads contrastivas, `Contrastive-LM/CLM-v0.1-8B` |
| JevK5 0.2 | `jevk5-0.2` | Qwen3.5-4B + LoRA destilada, `alibiserikbay/JevK5` |

**Confirmado em 2026-09-29 via `GET /v1/models`** (nomes reais, não suposição):

| Nome real | Descrição (da API) | Contexto |
|---|---|---|
| `openjev-latest` / `openjev-0.1` | DiffusionGemma 26B-A4B (NVFP4) sobre vLLM | — |
| `laya-1.0` | **checkpoint `laya-typed-decisions`** (ModernBERT-large, 421M) | 1.024 tokens |
| `verdict-1.4` | `rlcd-modernbert-151m` (ModernBERT-base + GLiClass, 151M) | 512 tokens, até 24 choices |
| `clm-v0.1` | Qwen3-8B-FP8 + heads contrastivas | 2.048 tokens |
| `jevk5-0.2` | Qwen3.5-4B + LoRA destilada | 16.384 tokens |

**⚠️ Achado crítico, confirma a suspeita do plano original**: `laya-1.0` no
codiv.ai usa `laya-typed-decisions` — o checkpoint que já identificamos como
**só inglês** (tags HF: sem `pt`, sem `multilingual`) quando revisamos o
OpenJev. **Não é o mesmo modelo** que `laya:multilingual` (mmBERT-base, 322M)
que roda local e que gerou todos os números da Fase 1-4. Comparar "laya-1.0
do codiv.ai" contra "laya local" seria comparar dois checkpoints distintos
com o mesmo nome de família — o mesmo erro que teríamos cometido com o
OpenJev se não tivéssemos revisado antes.

## Casos de amostra (22: 11 eco + 11 ultrassonografia, já selecionados)

Mesmo critério de sempre: `qualidade_dado: ok`, texto = `Conclusão` (nativa em
eco, derivada em ultrassonografia — ver §6 do documento técnico). Pasta
`old/` ignorada.

### Ecocardiografia (11) — 6 baixo/baixo_moderado + 5 moderado

| numero_relatorio | risco |
|---|---|
| REL-20260408-004 | baixo |
| REL-20260408-005 | baixo_moderado |
| REL-20260408-007 | baixo |
| REL-20260409-002 | baixo |
| REL-20260409-003 | baixo |
| REL-20260410-001 | baixo |
| REL-20260408-008 | moderado |
| REL-20260409-005 | moderado |
| REL-20260410-011 | moderado |
| REL-20260421-002 | moderado |
| REL-20260429-006 | moderado |

### Ultrassonografia (11) — 6 baixo + 5 moderado

| numero_relatorio | risco | Conclusão (derivada) |
|---|---|---|
| REL-20260406-002 | baixo | Exame abdominal sem alterações. |
| REL-20260406-004 | baixo | Exame abdominal sem alterações. |
| REL-20260406-005 | baixo | Exame abdominal sem alterações. |
| REL-20260406-006 | baixo | Exame abdominal sem alterações. |
| REL-20260406-007 | baixo | Exame abdominal sem alterações. |
| REL-20260407-001 | baixo | Exame abdominal sem alterações. |
| REL-20260406-003 | moderado | Achado em rins. Ver seção... |
| REL-20260407-009 | moderado | Achado em vesícula urinária. Ver seção... |
| REL-20260407-017 | moderado | Achado em rins. Ver seção... |
| REL-20260407-018 | moderado | Achados em rins e vesícula urinária. Ver seções... |
| REL-20260409-001 | moderado | Achado em rins. Ver seção... |

**Nota honesta**: em ultrassonografia, 5 dos 6 casos `baixo` têm a MESMA
frase exata ("Exame abdominal sem alterações.") e os `moderado` também
repetem padrão — já sabemos pelo EXP-002b que isso não discrimina com
laya/limiar 0.75. Se algum modelo do codiv.ai também não discriminar isso,
não é surpresa nova, confirma o problema de fundo (texto derivado, não o
modelo).

## Desenho do experimento

1. `GET /v1/models` no codiv.ai — confirmar nomes reais de modelo.
2. Mesmas perguntas tipadas já validadas (`internacao` noul, `gravidade`
   score, `causa_provavel` choice para eco / choice adaptado a órgãos para
   ultrassonografia).
3. Para cada um dos 5 modelos × 22 casos: 1 chamada a `POST /v1/systemone`,
   guardar `gravidade` (ou o score equivalente que cada modelo devolver —
   **não assumir que todos devolvem o mesmo shape**, verificar primeiro com
   1 caso por modelo).
4. Comparar contra laya local (Ollaya) já medido para os mesmos 22 casos —
   rodar também localmente para ter a mesma base de comparação (os números
   da Fase 1-4 são sobre 149/147/236 casos, não esses 22 exatos).
5. Com só 22 casos (11 vs 11), **não calcular "melhor limiar"** como nos
   experimentos grandes — a amostra é pequena para buscar limiar sem
   sobreajustar. Reportar os scores crus por caso e ordenar visualmente (o
   modelo separa baixo de moderado a olho, sim ou não?), não uma métrica de
   precisão/recall com n=22 que daria falsa confiança.
6. Modelos generativos (JevK5, CLM, possivelmente openjev) são mais lentos e
   podem ter custo real por token (diferente do laya, grátis local) —
   rodar esses por último e com menor prioridade se o orçamento da API key
   importar.

## O que NÃO fazer

- Não rodar o corpus completo (149/254) contra os 5 modelos sem antes
  confirmar que pelo menos um deles vale a pena nos 22 de amostra — é gasto
  de API real, não computação local grátis.
- Não assumir que "Laya 1.0" do codiv.ai é idêntico ao `laya:multilingual`
  local — mesmo nome de família, mas pode ser outro checkpoint/versão (já
  vimos com `laya-typed-decisions` vs `laya-multilingual` que nomes
  parecidos não são o mesmo modelo). Confirmar antes de comparar como se
  fossem o mesmo.

## Sondeio inicial executado (2026-09-29) — 1 caso normal + 1 grave por modelo

Mesmo texto nos 5: normal="Nada digno de nota.", grave="Valvopatia
mixomatosa mitral. Insuficiência valvar mitral de grau importante com
remodelamento de câmaras cardíacas esquerdas." Pergunta `gravidade` sozinha.

| Modelo | Normal | Grave | Separação | Confiança (normal/grave) |
|---|---|---|---|---|
| `laya-1.0` (codiv) | 0.72 | 1.48 | 0.76 | 0.12 / 0.22 |
| `verdict-1.4` | 0.78 | 1.17 | 0.39 | 0.04 / 0.02 |
| `jevk5-0.2` | 0.26 | 1.76 | 1.50 | 0.45 / 0.46 |
| `clm-v0.1` | 1.06 | 1.51 | 0.45 | 0.17 / 0.40 |
| **`openjev-latest`** | **0.01** | **1.97** | **1.96** | **0.96 / 0.88** |
| `laya:multilingual` (local, referência) | 0.29-0.65 (varia com o formato de `state`) | 1.48-1.64 | variável | — |

**`openjev-latest` domina claramente este sondeio mínimo** — separação quase
perfeita e confiança bem mais alta que o resto. `verdict-1.4` e `clm-v0.1`
mostram sinal fraco, não justificam prioridade. Com n=1 por classe isso é
indício, não prova.

**Decisão de recursos**: priorizar `openjev-latest` (+ `jevk5-0.2` como
segundo candidato) para o sondeio completo de 22 casos, em vez de gastar
orçamento de API rodando os 5 modelos igualmente — `verdict-1.4` e `clm-v0.1`
ficam de baixa prioridade salvo se o resultado completo dos outros dois
decepcionar.

## Próximo passo

Rodar os 22 casos (11 eco + 11 ultrassonografia) contra `openjev-latest` e
`jevk5-0.2` — 44 chamadas. Comparar contra laya local nos mesmos 22 casos
(rodar também localmente, não reusar os números da Fase 1-4 que são sobre
outro n). `verdict-1.4`/`clm-v0.1`/`laya-1.0` ficam pendentes, não
descartados.
