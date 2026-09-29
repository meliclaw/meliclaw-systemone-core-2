# Documento técnico: modelos de decisión tipada sobre laudos veterinarios

- **Estado:** técnico/funcional, vivo — refleja lo medido hasta 2026-09-29.
- **Alcance:** las 3 categorías del corpus `dataset/vet/train/`: ecocardiografia
  (468), ultrassonografia (254), outros (9).
- **Relacionado:** [gliner2-decide-vs-laya-eco.md](./gliner2-decide-vs-laya-eco.md)
  (experimento go/no-go, solo eco); `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/`
  (feature en producción, solo eco).

---

## 1. Los modelos

### 1.1 laya:multilingual (en producción)

| Campo | Valor |
|---|---|
| Encoder | mmBERT-base |
| Parámetros | 322M |
| Ventana de contexto | **1.024 tokens** |
| Formato servido | ONNX (F16), vía Ollaya |
| Calibración | **Sí** — el propio catálogo de Ollaya lo marca `calibrated` |
| Endpoint | `POST /v1/systemone` (TypeSafe-compatible), `meliclaw-systemone-core-2` |
| Capacidades | `choice`, `score`, `noul` (decisiones tipadas, un forward pass) |
| Licencia/origen | `huggingface.co/convaiinnovations/laya` |

Fuente: `meliclaw-systemone-core-2/docs/api.md` (specs verificadas contra la API real).

### 1.2 GLiNER2.5-multi-Decide (en evaluación, no integrado)

| Campo | Valor |
|---|---|
| Encoder | mDeBERTa-v2/v3-base (hidden=768, 12 capas) |
| Parámetros | 287.4M (confirmado vía API de Hugging Face, no el marketing) |
| Ventana de contexto | **512 tokens** |
| Arquitectura | `BoundaryExtractor` (propose-then-rerank span extraction — **no** un MLP simple sobre marcadores) |
| Formato servido | Librería `gliner2` (Python, CPU-first, no requiere GPU) |
| Calibración | **No** — `temperature=1.0, threshold=0.5` sin calibrar (declarado por el propio fornecedor) |
| Endpoint | `AutoExtractor.from_pretrained(...)`, local, sin servidor HTTP propio |
| Licencia/origen | Apache-2.0, `fastino/GLiNER2.5-multi-Decide` @ base `fastino/gliner2.5-multi-v1` |

**Nota de corrección**: el modelo `fastino/GLiNER2.5-Decide` (340M, DeBERTa-v3-large) es **solo inglés** — no sirve para este corpus (PT-BR). La variante correcta es `-multi-Decide`.

### 1.3 Comparación directa

| | laya:multilingual | GLiNER2.5-multi-Decide |
|---|---|---|
| Contexto | 1.024 tokens | 512 tokens |
| Parámetros | 322M | 287.4M |
| Calibrado | Sí | No |
| Benchmark del fornecedor (`fast-decisions`, genérico, no nuestro dominio) | Laya Router: 46.6% | 56.7% |
| Validado en nuestro dominio (eco, 149 casos reales, EXP-001, 2026-09-29) | Sí — recall=1.000, precisión=0.494, acurácia=0.718 | Sí — recall=1.000, **precisión=0.277**, **acurácia=0.282** — pierde |

**Resultado EXP-001 (ejecutado)**: en nuestro dominio real, GLiNER2.5-multi-Decide
tiene peor precisión y peor acurácia que laya, pese al benchmark genérico
favorable (56.7% vs 46.6%). El `score_sim` máximo entre los 41 casos que sí
debían internar es 0.493 — nunca cruza 0.5, el modelo nunca está "seguro" en
ningún caso grave. **No pasa el criterio de decisión — no se integra.**

---

## 2. Formatos de archivo de entrada, por categoría

Todos los archivos son Markdown con frontmatter YAML + cuerpo de texto libre en
PT-BR. Carpeta `old/` de cada categoría **siempre se ignora** (duplicados
obsoletos).

### 2.1 Ecocardiografia (468 archivos)

```yaml
---
numero_relatorio: REL-20260407-013
tipo_relatorio: ecocardiograma
especie: CANINO
paciente: Priscila
data_exame: "2026-04-07T13:58"
rotulo_origem: proposto_por_ia
dividir_em: treino
peso_kg: null
ecc: 5
fc_bpm: null
# ... campos clínicos estructurados (medidas, achados) ...
padrao_diastolico: restritivo
insuf_mitral: nenhuma
diagnosticos: [disfuncao_diastolica_restritiva]
risco: moderado          # baixo | baixo_moderado | moderado
qualidade_dado: revisar  # ok | revisar
---

Numero de relatorios: ...
Conteúdo

[secciones: Ventrículo Esquerdo, Ventrículo Direito, Valvas, Pericárdio,
Avaliação da função diastólica, Avaliação hemodinâmica — con medidas,
muchas veces vacías/`null`]

Conclusão

[1-3 frases, el veredicto clínico condensado]
```

- **Tiene sección `Conclusão` en el 100% de los casos** (verificado).
- `qualidade_dado: ok` en 149/468 (32%); `revisar` en 319/468 (68%) — mayoría
  con campos numéricos vacíos en el frontmatter, como el ejemplo de arriba.
- Longitud real de `Conclusão` (149 casos `ok`, medido): mediana 12 palabras,
  p95 42, máximo 49 — muy por debajo de cualquier límite de contexto.

### 2.2 Ultrassonografia (254 archivos)

```yaml
---
numero_relatorio: REL-20260406-002
tipo_relatorio: ultrassonografia
especie: CANINO
paciente: Bento
peso_kg: 37.5
figado: normal
figado_achado: null
baco: alterado
rim_esq_cm: 6.53
rim_dir_cm: 6.18
adrenal_esq_cm: [2.74, 0.81, 0.98]
diagnosticos: [exame_abdominal_sem_alteracoes]
risco: baixo              # baixo | moderado (no hay baixo_moderado en esta categoría)
qualidade_dado: ok
---

Conteúdo

Fígado – de dimensões preservadas...
Vesícula biliar - ...
Baço - ... (Achados relacionados con esplenomegalia...)
Estômago – ...
Alças intestinais - ...
Rins – ...
[... órgano por órgano ...]
Aorta e veia cava caudal com trajeto preservado.
```

- ~~**`Conclusão` NO existe en NINGÚN archivo (0/254, verificado)**~~ —
  **resuelto en 2026-09-29** (ver EXP-002 abajo): los 254 archivos ahora tienen
  `Conclusão` derivada de `diagnosticos` + órgano, marcada explícita
  `conclusao_origem: derivada_de_campos_estruturados` en el frontmatter — no
  es texto del veterinario original, es reformateo determinístico de campos
  que ya estaban estructurados en el mismo archivo. Script:
  `meliclaw-systemone-core-2/convert/ollaya_convert/families/gliner2/derive_conclusao_ultrasom.py`.
- `qualidade_dado: ok` en 236/254 (93%) — proporción mucho mejor que eco.
- `risco`: solo `baixo`/`moderado` (2 niveles, no 3 como en eco).
- **Implicación (resuelta)**: la estrategia "mandar solo la `Conclusão`" (usada
  en eco) ahora aplica también acá — ver §6, actividad de calidad de datos.

### 2.3 Outros (9 archivos)

```yaml
---
numero_relatorio: LAU-20260406-001
tipo_relatorio: outros
especie: CANINO
paciente: ALADIN
extracao_estruturada: nao_suportada_ainda
---

Conteúdo

Parede torácica: ...
Costelas: ...
Pleura: ...
Campos pulmonares: ...

Impressão diagnóstica:
Estruturas avaliadas sem alterações ultrassonográficas.
```

- `extracao_estruturada: nao_suportada_ainda` — sin campos clínicos
  estructurados, sin `risco`, sin `qualidade_dado`. Categoría catch-all.
- Header final **mixto**: algunos usan `Conclusão`, otros `Impressão
  diagnóstica:` — sin patrón único.
- **Fuera de alcance actual** — ni la feature de eco ni el experimento
  GLiNER2.5 lo tocan. 9 archivos es muestra insuficiente para cualquier
  medición de precisión/recall confiable.

---

## 3. Método: prompting / few-shot — no fine-tuning

**No hay entrenamiento en ningún punto de este trabajo.** laya y GLiNER2.5 son
modelos ya pre-entrenados por terceros (convaiinnovations, fastino). Lo único
que hacemos es *inferencia con preguntas tipadas* — pasarles texto + un
esquema de preguntas en cada llamada, sin tocar ni un peso del modelo.

### 3.1 Decisiones tipadas (laya, patrón `/v1/systemone`)

```json
{
  "model": "laya:multilingual",
  "state": {"numero_relatorio": "...", "laudo": "<texto>"},
  "questions": {
    "internacao": {"type": "noul", "instructions": "..."},
    "gravidade": {"type": "score", "instructions": "...", "criteria": [...]},
    "causa_provavel": {"type": "choice", "instructions": "...", "criteria": {...}}
  }
}
```

Un forward pass, sin generación de tokens. Respuesta: probabilidad calibrada
por pregunta (`noul` = sí/no, `score` = nivel ordinal, `choice` = categoría con
confianza). Esto es "prompting" en el sentido de: el diseño del texto de
`instructions`/`criteria` es lo único que se ajusta — nunca los pesos.

### 3.2 Few-shot — probado, EXP-004, resultado negativo (2026-09-29)

Probado vía el paquete `laya` nativo (mismo checkpoint `laya-multilingual`,
sin pasar por Ollaya), 2 ejemplos fijos (uno normal, uno grave) prependidos al
texto real, mismo formato de `state` que usa producción. Sobre 147 casos
(147 = 149 − los 2 usados como ejemplos):

| | Zero-shot | Few-shot (2 ejemplos) |
|---|---|---|
| Mediana positivos | 1.859 | 1.875 |
| Mediana negativos | 0.969 | **1.853** (casi igual a positivos) |
| Precisión (recall=1.0) | 0.333 | **0.274** |
| Acurácia | 0.456 | **0.279** |

**Few-shot empeora, no mejora.** Prependear ejemplos destruye la separación
entre grupos — la mediana de "no interna" salta de 0.969 a 1.853. Con un
encoder de clasificación (no generativo), no hay mecanismo de "aprender del
ejemplo" en una sola pasada — el texto extra solo diluye la lectura de
marcadores. **No usar few-shot con laya.**

Nota: estos números zero-shot (0.456/0.333) no coinciden con los de Fase 7 en
producción (0.718/0.494) — acá se mandó solo la pregunta `gravidade`, en
producción se mandan 3 preguntas juntas (`internacao`+`gravidade`+`causa_provavel`)
en el mismo request. Esa diferencia de payload probablemente explica el
corrimiento — no invalida la comparación few-shot vs zero-shot (mismo método
en ambos brazos), pero significa que estos números absolutos no reemplazan
los de Fase 7.

Evidencia: `evidencia_openjev_zeroshot.jsonl`, `evidencia_openjev_fewshot.jsonl`,
script `eval_exp004_fewshot.py`.

### 3.2.1 Hallazgo lateral: el formato de `state` cambia el resultado

Mismo texto ("Nada digno de nota."), mismo checkpoint, mismo runtime —
mandado como string plano da `gravidade=1.64`; envuelto en
`{"numero_relatorio":..., "laudo":...}` (formato real del Rust en producción)
da `gravidade=0.65`. El campo `numero_relatorio` dentro del JSON afecta lo que
el modelo "lee" como contenido clínico. Verificado en vivo contra el endpoint
real de Ollaya (`localhost:18135`), no es un artefacto del paquete Python.
Implicación: cualquier cambio futuro en cómo se arma `state` (agregar campos,
cambiar claves) puede correr el umbral de decisión sin que nadie lo note —
digno de un test de regresión, no solo de un valor fijo hardcodeado.

### 3.3 Por qué no fine-tuning

- Costo: requiere GPU dedicada, pipeline de entrenamiento, dataset etiquetado
  por veterinario real (no tenemos — ver ASM-001/Q-003 en
  `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`).
  Sin ground truth clínico confiable, entrenar es ajustar contra ruido.
- laya y GLiNER2.5.5-multi-Decide ya son modelos *fine-tuneados* por el
  fornecedor para la tarea de "decisión tipada" en general — la pregunta no es
  si el modelo sabe hacer el tipo de tarea, es si el *prompt específico*
  (`instructions`, `criteria`, qué texto de entrada) está bien diseñado para
  nuestro dominio. Eso se resuelve con prompting, no con entrenamiento.

---

## 4. Métricas medidas — ecocardiografia, laya:multilingual (Fase 7)

Único resultado con datos reales hasta ahora. Corpus: 149 casos
`qualidade_dado: ok`, ground truth = `risco == moderado` → `internacao`
esperada `true`.

| Entrada | Errores de llamada | Recall | Precisión | Acurácia |
|---|---|---|---|---|
| Laudo completo (sin extracción) | 39/149 (26%) — `STATE_TRUNCATED` | — | — | 0.118 (predijo `internação` para el 100%) |
| Solo `Conclusão` | 0/149 | **1.000** | 0.494 | 0.718 |

Distribución real de `gravidade` (score 0-2) sobre `Conclusão`:

| Grupo | n | min | p25 | mediana | p75 | max |
|---|---|---|---|---|---|---|
| Esperado interna (risco=moderado) | 41 | 0.781 | 1.623 | 1.756 | 1.823 | 1.962 |
| Esperado no interna | 108 | 0.164 | 0.553 | 0.625 | 1.470 | 1.944 |

Umbral usado en producción: `gravidade >= 0.75` (garantiza recall=1.000 —
prioridad clínica: nunca perder un caso real). El solapamiento entre grupos
(negativo máx 1.944 > positivo mín 0.781) es la causa directa de la precisión
baja (0.494) — no hay umbral que separe limpio.

---

## 6. Actividad de calidad de datos — Conclusão derivada para ultrassonografia (2026-09-29)

Resuelve EXP-002 (estado anterior de este documento). Registro de lo hecho,
para trazabilidad.

### 6.1 Problema

Ninguno de los 254 laudos de ultrassonografia tenía sección `Conclusão`
(0/254, verificado por grep). El laudo terminaba directo en el hallazgo del
último órgano evaluado. La estrategia que funciona en eco ("mandar solo la
Conclusão", recall=1.000/precisión=0.494 medido) no tenía qué extraer acá.

### 6.2 Opciones descartadas

- **Laudo completo**: ya sabemos por eco que satura la señal del modelo (0%
  discriminación, 26% de fallos por contexto) — descartada sin probar de
  nuevo, la causa raíz (ruido + longitud) es la misma en ultrassonografia.
- **Generar la Conclusão con un LLM** (yo redactando un resumen por archivo):
  descartada — fabricaría contenido clínico que el veterinario nunca escribió,
  contaminando el dataset de evaluación. Habría costado ~150-200k tokens
  adicionales sin necesidad.
- **Citar el texto libre `<orgao>_achado` del frontmatter**: probado primero,
  descartada al ver el resultado — ese campo ya viene truncado en la fuente
  (corta a mitad de palabra, ej. `"...com presença de áre"` en
  `REL-20260407-018.md`). Tomar la "primera frase" de ahí producía oraciones
  falsamente completas y engañosas (ver commit de prueba, revertido antes de
  aplicar).

### 6.3 Solución aplicada — derivación por reglas, sin texto libre

Script `meliclaw-systemone-core-2/convert/ollaya_convert/families/gliner2/derive_conclusao_ultrasom.py`:
deriva la Conclusão **solo** del campo `diagnosticos` (códigos ya
estructurados, confiables) + nombre del órgano — nunca del texto libre
truncado.

```python
# regla completa (simplificada):
if diagnosticos == ["exame_abdominal_sem_alteracoes"]:
    return "Exame abdominal sem alterações."
# si no, un órgano por código de diagnóstico (achado_renal → "rins", etc.)
return f"Achado em {orgao}. Ver seção correspondente no corpo do laudo para detalhes."
# (o "Achados em X e Y..." si hay más de un órgano)
```

Cada archivo modificado gana `conclusao_origem: derivada_de_campos_estruturados`
en el frontmatter — transparencia explícita de que no es texto del
veterinario original.

### 6.4 Resultado, verificado

- 254/254 archivos con `Conclusão` (antes: 0/254).
- 254/254 con `conclusao_origem` marcado.
- 254/254 con frontmatter YAML válido (verificado por parseo, no solo grep).
- Distribución de las 254 conclusiones generadas:

| Conclusão derivada | n |
|---|---|
| "Exame abdominal sem alterações." | 169 |
| Achado en rins | 23 |
| Achado en vesícula urinária | 19 |
| Achados en rins e vesícula urinária | 16 |
| Achado en fígado | 9 |
| Achados en fígado e rins | 6 |
| Achado en pâncreas | 5 |
| (combinaciones de 3 órganos) | 6 |

- Validado en 2 archivos de prueba (copia, no el original) antes de aplicar a
  los 254 reales.
- Commit: `0f08cd5d` en `agentic-platform` (rama
  `fix/vetsync-diagnostic-rustls-cross-compile`, no pusheado). 254 archivos,
  17.989 inserciones — eran archivos sin trackear en git hasta este commit.

### 6.5 Lo que esto NO resuelve

- La calidad clínica del texto derivado no fue revisada por un veterinario —
  mismo tipo de reserva que ASM-001 en la feature de eco. "Achado em rins" es
  deliberadamente genérico (no inventa gravedad ni detalle), pero sigue siendo
  una reformulación automática, no un juicio clínico.
- No valida que el modelo (laya o GLiNER2.5) rinda bien sobre este texto
  derivado — eso es EXP-002b, trabajo nuevo, no hecho todavía.

---

## 7. Preguntas abiertas / próximos pasos

| ID | Pregunta | Bloquea |
|---|---|---|
| ~~EXP-001~~ | **Resuelta 2026-09-29**: GLiNER2.5-multi-Decide sobre los mismos 149 casos de eco pierde contra laya (precisión 0.277 vs 0.494, acurácia 0.282 vs 0.718, mismo recall=1.000). No se integra. Evidencia: `evidencia_gliner2_resultado_eco.jsonl`, script `convert/ollaya_convert/families/gliner2/eval_exp001_eco.py`. | Cerrada |
| ~~EXP-002b~~ | **Resuelta 2026-09-29, negativa**: laya (umbral 0.75) predijo `internação:true` para el 100% de los 236 casos evaluados de ultrassonografia — cero discriminación (acurácia=precisión=0.356, igual a la tasa base de positivos). Confirma la sospecha: el texto derivado ("Achado em rins.") es demasiado genérico. Evidencia: `evidencia_exp002b_ultrasom.jsonl`, script `eval_exp002b_ultrasom.py`. **No usar la Conclusão derivada para decisión de internación en ultrassonografia sin cambiar de enfoque** — probable causa: umbral 0.75 fue calibrado para textos de eco (`gravidade` en 0.75-2.0 típico), y el texto genérico derivado ("Achado em X.") satura igual de alto que un texto detallado grave; necesitaría recalibrar umbral específico para esta categoría, o mandar más contexto (ej. los campos `_achado` truncados igual, aceptando el ruido) antes de descartar la vía. | Sigue bloqueando cualquier feature de decisión sobre ultrassonografia |
| EXP-003 | Outros (9 casos, headers mixtos) — ¿vale la pena una estrategia dedicada para 9 archivos, o se descarta la categoría? | No empezado, probablemente descartable por volumen |
| ~~EXP-004~~ | **Resuelta 2026-09-29**: few-shot (§3.2) empeora la discriminación de laya (acurácia 0.279 vs 0.456 zero-shot, mismo método). No usar. | Cerrada |

Todas las preguntas ASM/Q de la feature de eco en producción
(`vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`) siguen
abiertas y no se repiten acá.
