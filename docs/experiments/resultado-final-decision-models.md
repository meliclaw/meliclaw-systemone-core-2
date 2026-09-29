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
| **openjev-latest (codiv.ai)** | **Ultrassonografia (escala completa)** | **236** | **1.000** | **1.000** | **1.000** | 🟢 **Confirmado — separación perfecta, cero solapamiento** |
| jevk5-0.2 (codiv.ai) | Eco (muestra) | 11 | 1.000 | 0.714* | 0.818* | Similar a laya, no claramente mejor |
| **jevk5-0.2 (codiv.ai)** | **Ultrassonografia (escala completa)** | **236** | **1.000** | **1.000** | **1.000** | 🟢 **Confirmado — separación perfecta, cero solapamiento** |
| — | Outros | 9 | — | — | — | Fuera de alcance (muestra insuficiente) |

*Eco: precisión/acurácia con "mejor umbral" sobre n=11 — **sobreajuste
probable, muestra chica, no escalada** (ver §4.1). Ultrassonografia: números
reales sobre los 236 casos completos, no sondeo.

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

## 4. codiv.ai — sondeo (22 casos) + escalado completo de ultrassonografia (236 casos)

**Decisión de alcance (2026-09-29)**: escalar `openjev-latest`/`jevk5-0.2` a
eco (147) + ultrassonografia (236) completos tenía costo real — rate-limit
de 10s/llamada. Dado que el sondeo de 11 mostró ventaja clara solo en
ultrassonografia (eco salió similar a laya), se priorizó escalar **solo
ultrassonografia** a los 236 casos completos (`qualidade_dado: ok`) — eco
queda en el sondeo de 11, sin escalar (no había hipótesis que confirmar).

### 4.1 Ecocardiografia (11 casos, sondeo, no escalado) — resultado similar a laya

| Modelo | Positivos (score) | Negativos (score) |
|---|---|---|
| laya (local) | 1.62 – 1.87 | 0.60 – 1.89 |
| openjev-latest | 1.06 – 2.00 | 0.02 – 1.98 |
| jevk5-0.2 | 1.52 – 1.85 | 0.13 – 1.55 |

Los 3 modelos tienen solapamiento visible en eco — ninguno claramente mejor
que laya en esta muestra. No se escaló por falta de ventaja aparente.

### 4.2 Ultrassonografia — **CONFIRMADO a escala completa (236/236 casos, sin errores)**

| Modelo | Recall | Precisión | Acurácia | Positivos (score) | Negativos (score) |
|---|---|---|---|---|---|
| laya (local, referencia) | 1.000 | 0.457 | 0.576 | 0.886 – 1.417 | 0.785 – 0.977 |
| **openjev-latest** | **1.000** | **1.000** | **1.000** | **0.866 – 0.997** | **0.005 – 0.030** |
| **jevk5-0.2** | **1.000** | **1.000** | **1.000** | **0.422 – 0.941** | **0.011 (casi constante)** |

**Ya no es indicio — es resultado confirmado.** Sobre los 236 casos reales,
`openjev-latest` y `jevk5-0.2` separan con **precisión y acurácia perfectas
(1.000)** — cero falsos positivos, cero falsos negativos. Margen entre
grupos: negativos de openjev nunca superan 0.030, positivos nunca bajan de
0.866 — no hay solapamiento en ningún punto de los 236 casos. `jevk5-0.2`
da un score casi idéntico (~0.0106) para casi todos los negativos —
sugiere que distingue de forma casi binaria "Exame abdominal sem
alterações." (texto idéntico en 169/236 casos) de cualquier "Achado em X."

laya mejoró levemente respecto a EXP-002b (0.576 vs 0.356 de acurácia) al
usar "mejor umbral" en vez del umbral fijo 0.75 de producción, pero sigue
muy por debajo de los otros dos — su rango de positivos y negativos se
solapa (positivo mín 0.886, negativo máx 0.977).

**Esto sugiere fuertemente que el problema de ultrassonografia no es el
texto genérico en sí — es que laya específicamente no lo procesa bien.**
`openjev-latest`/`jevk5-0.2` sí distinguen ese mismo texto de forma
prácticamente perfecta.

**Reserva metodológica, sigue en pie**: el ground truth (`risco` en el
frontmatter) es `rotulo_origem: proposto_por_ia` — propuesto por una regla
automática, no confirmado por un veterinario real. Una separación perfecta
contra una etiqueta también generada por IA no es prueba de acierto
clínico, es prueba de que el modelo reproduce la misma regla/patrón que
generó la etiqueta. Sigue bloqueado por ASM-001/Q-003 antes de cualquier
uso real.

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
   (236 casos).
3. **GLiNER2.5-multi-Decide y few-shot quedan descartados** para eco —
   evidencia real, no suposición.
4. **`openjev-latest`/`jevk5-0.2` resuelven ultrassonografia — confirmado a
   escala completa (236/236, precisión y acurácia = 1.000, §4.2)**, no ya
   solo un indicio de 11 casos. Es el resultado más fuerte de toda la
   sesión. **Pero** el ground truth es `rotulo_origem: proposto_por_ia`
   (regla automática, no veterinario) — una separación perfecta contra una
   etiqueta también generada por IA prueba que el modelo reproduce el
   mismo patrón que generó la etiqueta, no que acierta clínicamente.
   Candidato fuerte a validación clínica real antes de cualquier uso en
   producción — ya no a más experimentos de sondeo.
5. **Ninguno de estos resultados fue validado por un veterinario real** —
   sigue pendiente en todos los experimentos, y es el paso que de verdad
   falta ahora para ultrassonografia (ver ASM-001/Q-003 en
   `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`).

## Evidencia (jsonl + scripts, todos en este directorio)

- `evidencia_gliner2_resultado_eco.jsonl` + `eval_exp001_eco.py` (GLiNER2.5, eco)
- `evidencia_openjev_zeroshot.jsonl` + `evidencia_openjev_fewshot.jsonl` + `eval_exp004_fewshot.py` (few-shot, eco)
- `evidencia_exp002b_ultrasom.jsonl` + `eval_exp002b_ultrasom.py` (laya, ultrassonografia)
- `evidencia_codiv_sondeo22.jsonl` + `eval_codiv_sondeo22.py` (sondeo codiv.ai, 22 casos, eco+ultrassom)
- `evidencia_codiv_ultrasom_236.jsonl` + `eval_codiv_ultrasom_236.py` (escalado completo, ultrassonografia, 236 casos)
