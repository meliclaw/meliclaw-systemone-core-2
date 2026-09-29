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
| **openjev-latest (codiv.ai)** | **Ecocardiografia (escala completa)** | **149** | **1.000** | **0.683** | **0.872** | 🟢 **Supera a laya** |
| **openjev-latest (codiv.ai)** | **Ultrassonografia (escala completa)** | **236** | **1.000** | **1.000** | **1.000** | 🟢 **Separación perfecta, cero solapamiento** |
| jevk5-0.2 (codiv.ai) | Ecocardiografia (escala completa) | 149 | 1.000 | 0.651 | 0.852 | 🟢 Supera a laya |
| **jevk5-0.2 (codiv.ai)** | **Ultrassonografia (escala completa)** | **236** | **1.000** | **1.000** | **1.000** | 🟢 **Separación perfecta, cero solapamiento** |
| — | Outros | 9 | — | — | — | Fuera de alcance (muestra insuficiente) |

Todos los números de codiv.ai en esta tabla son sobre el corpus completo
(`qualidade_dado: ok`), no sondeo — ver §4.

**Conclusión de una línea**: contra lo que sugería el sondeo inicial de 11
casos ("sin ventaja clara"), a escala completa `openjev-latest` **supera a
laya en las dos categorías** — no solo en ultrassonografia. El n=11 no era
representativo. GLiNER2.5 y few-shot con laya siguen descartados.

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

**Actualización (§4.1): `openjev-latest` (codiv.ai) supera este resultado
sobre los mismos 149 casos** — acurácia 0.872 vs 0.718, precisión 0.683 vs
0.494, mismo recall perfecto. laya deja de ser la única opción con buen
desempeño en eco.

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

## 4. codiv.ai — escalado completo (eco 149 + ultrassonografia 236)

**Decisión de alcance (2026-09-29)**: escalar `openjev-latest`/`jevk5-0.2` a
eco + ultrassonografia completos tenía costo real — rate-limit de
10s/llamada, ~50min + ~79min de corridas pagadas. Se hizo en dos pasadas: primero
ultrassonografia (el sondeo de 11 mostraba separación perfecta), y al
confirmarse, también eco — aunque el sondeo de 11 en eco sugería "sin
ventaja clara", se decidió escalar igual para no confiar en una muestra tan
chica. **La decisión de escalar eco fue correcta: el sondeo de 11 estaba
equivocado.**

### 4.1 Ecocardiografia — **escalado completo (149/149 casos, sin errores) — openjev supera a laya**

| Modelo | Recall | Precisión | Acurácia | Positivos (score) | Negativos (score) |
|---|---|---|---|---|---|
| laya (local, producción) | 1.000 | 0.494 | 0.718 | 0.781 – 1.962 | 0.164 – 1.944 |
| **openjev-latest** | **1.000** | **0.683** | **0.872** | **1.001 – 1.999** | **0.003 – 1.995** |
| jevk5-0.2 | 1.000 | 0.651 | 0.852 | 0.748 – 1.855 | 0.119 – 1.564 |

El sondeo de 11 casos había sugerido "sin ventaja clara" — **estaba
equivocado**. A escala completa, `openjev-latest` mejora la acurácia de
laya en +0.154 y la precisión en +0.189 (menos falsos positivos, misma
recall perfecta). `jevk5-0.2` también mejora, algo menos.

Los rangos de score siguen solapándose para los tres modelos (a diferencia
de la separación total vista en ultrassonografia) — la mejora viene de una
mejor distribución interna, no de una separación limpia. Este es un
resultado más "normal"/incremental que el de ultrassonografia, no un salto
cualitativo.

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

1. **`openjev-latest` (codiv.ai) supera a `laya:multilingual` en las DOS
   categorías, confirmado a escala completa** — eco: acurácia 0.872 vs
   0.718 (149 casos, §4.1); ultrassonografia: acurácia 1.000 vs 0.356-0.576
   (236 casos, §4.2). El sondeo inicial de 11 casos en eco sugería "sin
   ventaja" — estaba equivocado; la decisión de escalar igual fue correcta.
2. **laya:multilingual sigue siendo lo único en producción hoy**, pero ya
   no es la mejor opción medida — es la opción con historial (Fase 1-4,
   `vetsync-diagnostic`), no la de mejor desempeño.
3. **GLiNER2.5-multi-Decide y few-shot con laya quedan descartados** para
   eco — evidencia real, no suposición.
4. **Ultrassonografia con laya no tiene vía funcional** (§2.2) — pero
   `openjev-latest`/`jevk5-0.2` sí la resuelven, con separación perfecta.
5. **Reserva que aplica a TODO lo anterior, no solo a ultrassonografia**:
   el ground truth (`risco`) es `rotulo_origem: proposto_por_ia` en ambas
   categorías — nunca confirmado por un veterinario real. Que
   `openjev-latest` prediga mejor una etiqueta generada por IA no prueba
   acierto clínico, prueba que reproduce mejor el patrón que generó esa
   etiqueta. Esto aplica igual a los números de eco que ya estaban en
   producción (laya) — nunca fueron validados tampoco.
6. **Próximo paso real ya no es más experimentos de sondeo/escalado** — es
   validación clínica por un veterinario (ASM-001/Q-003 en
   `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`),
   y evaluar migrar `vetsync-diagnostic` de laya a `openjev-latest` como
   backend, sujeto a esa validación y a confirmar costo/latencia real de
   la API de codiv.ai en producción (hoy solo medido con rate-limit de
   sondeo, no con volumen de tráfico real).

## Evidencia (jsonl + scripts, todos en este directorio)

- `evidencia_gliner2_resultado_eco.jsonl` + `eval_exp001_eco.py` (GLiNER2.5, eco)
- `evidencia_openjev_zeroshot.jsonl` + `evidencia_openjev_fewshot.jsonl` + `eval_exp004_fewshot.py` (few-shot, eco)
- `evidencia_exp002b_ultrasom.jsonl` + `eval_exp002b_ultrasom.py` (laya, ultrassonografia)
- `evidencia_codiv_sondeo22.jsonl` + `eval_codiv_sondeo22.py` (sondeo codiv.ai, 22 casos, eco+ultrassom)
- `evidencia_codiv_ultrasom_236.jsonl` + `eval_codiv_ultrasom_236.py` (escalado completo, ultrassonografia, 236 casos)
- `evidencia_codiv_eco_149.jsonl` + `eval_codiv_eco_149.py` (escalado completo, ecocardiografia, 149 casos)
