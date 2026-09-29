# Plan: experimentos multi-modelo vía API de codiv.ai

- **Estado:** planeado, no ejecutado.
- **Objetivo:** sondear rápido (22 casos, no el corpus completo) si algún
  modelo servido por codiv.ai (OpenJev, Laya, Verdict, CLM, JevK5) discrimina
  mejor que laya local (Ollaya) ya medido en Fases 1-4.
- **Relacionado:** `decision-models-laudos-veterinarios.md` (métricas ya
  medidas), `gliner2-decide-vs-laya-eco.md`.

## Seguridad — antes de tocar código

El usuario pegó una API key real en el chat (`sk-codiv-...`). **Se recomienda
rotarla** antes de usarla en cualquier script — quedó expuesta en el
historial de esta sesión. Cuando se use:

- Nunca hardcodeada en código ni committeada — solo `export TYPESAFE_API_KEY=...`
  en shell, o `.env` local (gitignored, igual que `vetsync-diagnostic/.env`).
- Nunca logueada (ni en stdout de scripts de eval, ni en jsonl de evidencia).

## Modelos a probar (5, vía `typesafe-sdk` / `POST /v1/systemone`)

Los 5 nombres coinciden exactamente con los backends documentados en
`meliclaw-systemone-core/openjev/encoders.py` (docstring) — codiv.ai parece
ser un hosting gerenciado de ese mismo stack, no modelos nuevos:

| Modelo | Backend real (según encoders.py) | Checkpoint / arquitectura |
|---|---|---|
| `openjev-latest` (o similar) | vLLM + DiffusionGemma (generativo, el más pesado) | modelo grande, no encoder |
| Laya 1.0 | `laya-1.0`, `laya` package | ModernBERT-large/mmBERT-base — **mismo que ya medimos local** |
| Verdict 1.4 | `verdict-1.4` | ModernBERT-base + GLiClass, 151M, `heman10x/rlcd-modernbert-151m` |
| CLM 0.1 | `clm-v0.1` | Qwen3-8B embeddings + heads contrastivas, `Contrastive-LM/CLM-v0.1-8B` |
| JevK5 0.2 | `jevk5-0.2` | Qwen3.5-4B + LoRA destilada, `alibiserikbay/JevK5` |

**Confirmado 2026-09-29 vía `GET /v1/models`** (nombres reales, no asunción):

| Nombre real | Descripción (de la API) | Contexto |
|---|---|---|
| `openjev-latest` / `openjev-0.1` | DiffusionGemma 26B-A4B (NVFP4) sobre vLLM | — |
| `laya-1.0` | **checkpoint `laya-typed-decisions`** (ModernBERT-large, 421M) | 1.024 tokens |
| `verdict-1.4` | `rlcd-modernbert-151m` (ModernBERT-base + GLiClass, 151M) | 512 tokens, hasta 24 choices |
| `clm-v0.1` | Qwen3-8B-FP8 + heads contrastivas | 2.048 tokens |
| `jevk5-0.2` | Qwen3.5-4B + LoRA destilada | 16.384 tokens |

**⚠️ Hallazgo crítico, confirma la sospecha del plan original**: `laya-1.0`
en codiv.ai usa `laya-typed-decisions` — el checkpoint que ya identificamos
como **solo inglés** (tags HF: sin `pt`, sin `multilingual`) cuando revisamos
OpenJev. **No es el mismo modelo** que `laya:multilingual` (mmBERT-base,
322M) que corre local y que generó todos los números de Fase 1-4. Comparar
"laya-1.0 de codiv.ai" contra "laya local" sería comparar dos checkpoints
distintos con el mismo nombre de familia — mismo error que hubiera cometido
con OpenJev si no lo hubiéramos revisado antes.

## Casos de muestra (22: 11 eco + 11 ultrassonografia, ya seleccionados)

Mismo criterio de siempre: `qualidade_dado: ok`, texto = `Conclusão` (nativa
en eco, derivada en ultrassonografia — ver §6 del doc técnico). Carpeta
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

**Nota honesta**: en ultrassonografia, 5 de los 6 casos `baixo` tienen la
MISMA frase exacta ("Exame abdominal sem alterações.") y los `moderado`
también repiten patrón — ya sabemos por EXP-002b que esto no discrimina con
laya/umbral 0.75. Si algún modelo de codiv.ai tampoco discrimina esto, no es
sorpresa nueva, confirma el problema de fondo (texto derivado, no el modelo).

## Diseño del experimento

1. `GET /v1/models` en codiv.ai — confirmar nombres reales de modelo.
2. Mismas preguntas tipadas ya validadas (`internacao` noul, `gravidade`
   score, `causa_provavel` choice para eco / choice adaptado a órganos para
   ultrassonografia).
3. Para cada uno de los 5 modelos × 22 casos: 1 llamada a
   `POST /v1/systemone`, guardar `gravidade` (o el score equivalente que
   devuelva cada modelo — **no asumir que todos devuelven el mismo shape**,
   verificar primero con 1 caso por modelo).
4. Comparar contra laya local (Ollaya) ya medido para los mismos 22 casos —
   correr también localmente para tener la misma base de comparación (los
   números de Fase 1-4 son sobre 149/147/236 casos, no estos 22 exactos).
5. Con solo 22 casos (11 vs 11), **no calcular "mejor umbral"** como en los
   experimentos grandes — la muestra es chica para buscar umbral sin
   sobreajustar. Reportar los scores crudos por caso y ordenar visualmente
   (¿el modelo separa baixo de moderado al ojo, sí o no?), no una métrica de
   precisión/recall con n=22 que daría falsa confianza.
6. Modelos generativos (JevK5, CLM, posiblemente openjev) son más lentos y
   pueden tener costo por token real (a diferencia de laya, gratis
   local) — correr estos últimos y en menor prioridad si el presupuesto de
   la API key importa.

## Qué NO hacer

- No correr el corpus completo (149/254) contra los 5 modelos sin antes
  confirmar que al menos uno de ellos vale la pena en los 22 de muestra — es
  gasto de API real, no cómputo local gratis.
- No asumir que "Laya 1.0" de codiv.ai es idéntico al `laya:multilingual`
  local — mismo nombre de familia, pero puede ser otro checkpoint/versión
  (ya vimos con `laya-typed-decisions` vs `laya-multilingual` que nombres
  parecidos no son el mismo modelo). Confirmar antes de comparar como si
  fueran el mismo.

## Sondeo inicial ejecutado (2026-09-29) — 1 caso normal + 1 grave por modelo

Mismo texto en los 5: normal="Nada digno de nota.", grave="Valvopatia
mixomatosa mitral. Insuficiência valvar mitral de grau importante com
remodelamento de câmaras cardíacas esquerdas." Pregunta `gravidade` sola.

| Modelo | Normal | Grave | Separación | Confianza (normal/grave) |
|---|---|---|---|---|
| `laya-1.0` (codiv) | 0.72 | 1.48 | 0.76 | 0.12 / 0.22 |
| `verdict-1.4` | 0.78 | 1.17 | 0.39 | 0.04 / 0.02 |
| `jevk5-0.2` | 0.26 | 1.76 | 1.50 | 0.45 / 0.46 |
| `clm-v0.1` | 1.06 | 1.51 | 0.45 | 0.17 / 0.40 |
| **`openjev-latest`** | **0.01** | **1.97** | **1.96** | **0.96 / 0.88** |
| `laya:multilingual` (local, referencia) | 0.29-0.65 (varía con formato de `state`) | 1.48-1.64 | variable | — |

**`openjev-latest` domina claramente este sondeo mínimo** — separación casi
perfecta y confianza mucho más alta que el resto. `verdict-1.4` y `clm-v0.1`
muestran señal débil, no justifican prioridad. Con n=1 por clase esto es
indicio, no prueba.

**Decisión de recursos**: priorizar `openjev-latest` (+ `jevk5-0.2` como
segundo candidato) para el sondeo completo de 22 casos, en vez de gastar
presupuesto de API corriendo los 5 modelos por igual — `verdict-1.4` y
`clm-v0.1` quedan de baja prioridad salvo que el resultado completo de los
otros dos decepcione.

## Próximo paso

Correr los 22 casos (11 eco + 11 ultrassonografia) contra `openjev-latest` y
`jevk5-0.2` — 44 llamadas. Comparar contra laya local en los mismos 22 casos
(correr localmente, no reusar números de Fase 1-4 que son sobre otro n).
`verdict-1.4`/`clm-v0.1`/`laya-1.0` quedan pendientes, no descartados.
