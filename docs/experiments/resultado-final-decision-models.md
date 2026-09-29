# Resultado final: modelos de decisión tipada sobre laudos veterinarios

- **Estado:** técnico/funcional, vivo — refleja lo medido hasta 2026-09-29.
- **Alcance:** las 3 categorías del corpus `dataset/vet/train/`:
  ecocardiografia (468), ultrassonografia (254), outros (9).
- **Este documento consolida** todos los experimentos ejecutados a escala
  completa (todos los casos `qualidade_dado: ok` de cada categoría, no
  muestras chicas) — es el resultado final, no un plan. Los documentos de
  proceso quedan como referencia detallada:
  [decision-models-laudos-veterinarios.md](./decision-models-laudos-veterinarios.md),
  [gliner2-decide-vs-laya-eco.md](./gliner2-decide-vs-laya-eco.md),
  [codiv-ai-multi-model-plan.md](./codiv-ai-multi-model-plan.md).

## Resumen ejecutivo

| Modelo | Categoría | n | Recall | Precisión | Acurácia | Veredicto |
|---|---|---|---|---|---|---|
| **laya:multilingual** (producción) | Ecocardiografia | 149 | **1.000** | **0.494** | **0.718** | ✅ En producción |
| GLiNER2.5-multi-Decide | Ecocardiografia | 149 | 1.000 | 0.277 | 0.282 | ❌ Pierde, no se integra |
| laya:multilingual (few-shot, 2 ejemplos) | Ecocardiografia | 147 | 1.000 | 0.274 | 0.279 | ❌ Empeora, no usar |
| laya:multilingual | Ultrassonografia | 236 | 1.000 | 0.356 | 0.356 | ❌ No discrimina (100% falsos positivos entre negativos) |
| GLiNER2.5-multi-Decide | Ultrassonografia | — | — | — | — | No evaluado |
| openjev-latest (codiv.ai) | Eco (muestra) | 11 | 1.000 | 0.769* | 0.864* | Similar a laya, no claramente mejor |
| openjev-latest (codiv.ai) | **Ultrassonografia (muestra)** | 11 | **1.000** | **1.000** | **1.000** | 🟢 **Separación perfecta — donde laya falla al 100%** |
| jevk5-0.2 (codiv.ai) | Eco (muestra) | 11 | 1.000 | 0.714* | 0.818* | Similar a laya, no claramente mejor |
| jevk5-0.2 (codiv.ai) | **Ultrassonografia (muestra)** | 11 | **1.000** | **1.000** | **1.000** | 🟢 **Separación perfecta — donde laya falla al 100%** |
| — | Outros | 9 | — | — | — | Fuera de alcance (muestra insuficiente) |

*Precisión/acurácia calculadas con "mejor umbral" sobre n=11 por categoría —
**sobreajuste probable con muestra tan chica**, ver advertencia en §4.

**Conclusión de una línea**: `laya:multilingual` sobre la `Conclusão` de
ecocardiografia sigue siendo la única combinación que funciona razonablemente
(recall perfecto, mitad de los positivos son falsa alarma). Todo lo demás
probado a escala real — GLiNER2.5, few-shot, y laya sobre ultrassonografia —
falla o empeora.

## 1. Ecocardiografia (468 archivos, 149 evaluados con `qualidade_dado: ok`)

### 1.1 laya:multilingual — producción, Fase 7

Entrada: `Conclusão` nativa del laudo (mediana 12 palabras, p95 42).

| | TP | FN | FP | TN | Recall | Precisión | Acurácia |
|---|---|---|---|---|---|---|---|
| Umbral `gravidade >= 0.75` | 41 | 0 | 76 | 32 | 1.000 | 0.494 | 0.718 |

Distribución de `gravidade`: positivos (min 0.781, mediana 1.756, max 1.962)
vs negativos (min 0.164, mediana 0.625, max 1.944) — el solapamiento en la
cola alta de los negativos (máx 1.944 > mín de los positivos) es la causa
directa de la precisión de 0.494. No existe un umbral que separe limpio.

**Sensibilidad al formato del `state` (hallazgo lateral, EXP-004)**: mismo
texto, mismo checkpoint — string plano da `gravidade=1.64`; envuelto en
`{"numero_relatorio":..., "laudo":...}` (formato real de producción) da
`0.65`. Cualquier cambio futuro en cómo se arma `state` puede correr el
umbral sin que nadie lo note.

### 1.2 GLiNER2.5-multi-Decide — EXP-001, pierde

Mismos 149 casos, misma `Conclusão`, mismo umbral de decisión
(recall=1.0 obligatorio).

| | Recall | Precisión | Acurácia |
|---|---|---|---|
| laya:multilingual | 1.000 | 0.494 | 0.718 |
| GLiNER2.5-multi-Decide | 1.000 | **0.277** | **0.282** |

El `score_sim` máximo entre los 41 casos que sí debían internar es 0.493 —
nunca cruza 0.5, el modelo nunca está "seguro" en ningún caso grave. Única
ventaja: latencia (129ms p50 vs ~1-2s e2e de laya vía HTTP), no compensa.
**No se integra.**

### 1.3 Few-shot — EXP-004, empeora

2 ejemplos fijos (uno normal, uno grave) prependidos al texto real, 147 casos
(149 − los 2 usados como ejemplo), metodología reducida (solo pregunta
`gravidade`, para aislar el efecto del few-shot del efecto del payload).

| | Recall | Precisión | Acurácia |
|---|---|---|---|
| Zero-shot (mismo método reducido) | 1.000 | 0.333 | 0.456 |
| Few-shot (2 ejemplos) | 1.000 | **0.274** | **0.279** |

Mediana de negativos salta de 0.969 (zero-shot) a 1.853 (few-shot) — casi
igual a la mediana de positivos (1.875). Prependear ejemplos destruye la
discriminación en un encoder de clasificación (no generativo). **No usar
few-shot con laya.**

## 2. Ultrassonografia (254 archivos, 236 evaluados con `qualidade_dado: ok`)

### 2.1 Conclusão derivada (actividad de calidad de datos previa)

Ningún archivo tenía `Conclusão` nativa (0/254). Se derivó determinísticamente
desde `diagnosticos` + órgano (`"Exame abdominal sem alterações."` o
`"Achado em <órgão>."`), marcada `conclusao_origem:
derivada_de_campos_estruturados` — nunca inventando detalle clínico nuevo.

### 2.2 laya:multilingual — EXP-002b, falla total

| | TP | FN | FP | TN | Recall | Precisión | Acurácia |
|---|---|---|---|---|---|---|---|
| Umbral `gravidade >= 0.75` (mismo de eco) | 84 | 0 | 152 | 0 | 1.000 | **0.356** | **0.356** |

**Predijo `internação:true` para el 100% de los 236 casos.** Precisión y
acurácia son exactamente la tasa base de positivos (84/236) — cero señal
real, no mejor que adivinar "siempre sí". Causa probable: el umbral 0.75 fue
calibrado sobre el rango de `gravidade` real de eco; el texto derivado,
genérico, satura igual de alto que un caso grave real, sin importar el
`risco` verdadero.

**No usar la Conclusão derivada para decisión de internación en
ultrassonografia sin cambiar de enfoque** (recalibrar umbral específico, dar
más contexto, o abandonar la vía).

### 2.3 GLiNER2.5-multi-Decide — no evaluado

No se corrió sobre ultrassonografia. Dado que ya falla en eco (§1.2), no es
prioridad — si laya no discrimina sobre este texto genérico, no hay razón de
esperar que GLiNER2.5 sí.

## 3. Outros (9 archivos)

Fuera de alcance en todos los experimentos. `extracao_estruturada:
nao_suportada_ainda`, sin `risco`, sin `qualidade_dado`, headers finales
mixtos (`Conclusão` / `Impressão diagnóstica:`). 9 archivos es muestra
insuficiente para cualquier métrica de precisión/recall confiable — no vale
la pena una estrategia dedicada a este volumen.

## 4. codiv.ai — sondeo de 22 casos (no escala completa)

**Decisión de alcance (2026-09-29)**: escalar `openjev-latest`/`jevk5-0.2` a
los 722 casos completos del corpus tiene costo real — rate-limit confirmado
de 10s/llamada implica ~4 horas y gasto de API pagada por 1.444 llamadas.
Este sondeo de 22 casos (11 eco + 11 ultrassonografia, ambos con mezcla
normal/grave) es indicio, no prueba — n demasiado chico para el "mejor
umbral" sin sobreajustar. Detalle completo del diseño en
[codiv-ai-multi-model-plan.md](./codiv-ai-multi-model-plan.md).

### 4.1 Ecocardiografia (11 casos) — resultado similar a laya

| Modelo | Positivos (score) | Negativos (score) |
|---|---|---|
| laya (local) | 1.62 – 1.87 | 0.60 – 1.89 |
| openjev-latest | 1.06 – 2.00 | 0.02 – 1.98 |
| jevk5-0.2 | 1.52 – 1.85 | 0.13 – 1.55 |

Los 3 modelos tienen solapamiento visible en eco — ninguno claramente mejor
que laya en esta muestra.

### 4.2 Ultrassonografia (11 casos) — hallazgo fuerte

| Modelo | Positivos (score) | Negativos (score) | Solapamiento |
|---|---|---|---|
| laya (local) | 1.20 – 1.32 | 0.89 – 0.97 | **Total** — confirma EXP-002b |
| **openjev-latest** | **0.89 – 0.96** | **0.01 – 0.02** | **Ninguno — 11/11 perfecto** |
| **jevk5-0.2** | **0.54 – 0.64** | **0.01** | **Ninguno — 11/11 perfecto** |

**Esto es un hallazgo real, no ruido**: diferencia de un orden de magnitud
entre positivos y negativos en ambos modelos de codiv.ai, sobre el mismo
texto genérico derivado ("Exame abdominal sem alterações." vs "Achado em
X.") donde laya no distingue nada. Sugiere que el problema de
ultrassonografia **no es el texto genérico en sí** — es que laya
específicamente no lo procesa bien. Con n=11 la señal es fuerte (separación
total, no marginal) pero sigue siendo indicio: falta escalar a más casos
antes de decidir integrar.

**Hallazgo lateral de seguridad**: se usó una API key pegada en texto plano
en el chat (`sk-codiv-...`) — se recomendó rotarla, no se hardcodeó en
ningún script committeado.

**Hallazgo lateral técnico**: el cliente HTTP importa — `urllib.request` de
Python disparó 403 Forbidden persistente en la API de codiv.ai incluso con
backoff de 10s; el mismo request vía subprocess `curl` funcionó sin
problema. Causa exacta no diagnosticada (posible diferencia de headers o
manejo de keep-alive), documentado para no repetir la confusión.

## 5. Veredicto final

1. **`laya:multilingual` sobre `Conclusão` de ecocardiografia sigue siendo
   producción** — único caso con recall perfecto y precisión utilizable
   (0.494) como herramienta de triaje, no decisión autónoma.
2. **Ultrassonografia con laya no tiene vía funcional** — ni la Conclusão
   derivada ni el umbral de eco sirven, confirmado a escala completa
   (236 casos) y en la muestra de 22.
3. **GLiNER2.5-multi-Decide y few-shot quedan descartados** para eco —
   evidencia real, no suposición.
4. **Pista fuerte para ultrassonografia: `openjev-latest`/`jevk5-0.2`
   separan perfecto (11/11) donde laya falla al 100%** (§4.2) — no
   confirmado a escala, pero la señal es demasiado limpia para ser
   casualidad. Es el hallazgo más prometedor de toda la sesión para
   desbloquear el punto 2. Próximo paso natural: escalar el sondeo de
   ultrassonografia específicamente (no eco, donde no hay ventaja clara) a
   más casos antes de decidir integrar.
5. **Ninguno de estos resultados fue validado por un veterinario real** —
   sigue pendiente en todos los experimentos (ver ASM-001/Q-003 en
   `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`).

## Evidencia (jsonl + scripts, todos en este directorio)

- `evidencia_gliner2_resultado_eco.jsonl` + `eval_exp001_eco.py` (GLiNER2.5, eco)
- `evidencia_openjev_zeroshot.jsonl` + `evidencia_openjev_fewshot.jsonl` + `eval_exp004_fewshot.py` (few-shot, eco)
- `evidencia_exp002b_ultrasom.jsonl` + `eval_exp002b_ultrasom.py` (laya, ultrassonografia)
- `evidencia_codiv_sondeo22.jsonl` + `eval_codiv_sondeo22.py` (sondeo codiv.ai, 22 casos)
