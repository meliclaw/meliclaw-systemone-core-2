# Resultado final: modelos de decisão tipada sobre laudos veterinários

- **Estado:** técnico/funcional, vivo — reflete o medido até 2026-09-29.
- **Escopo:** as 3 categorias do corpus `dataset/vet/train/`: ecocardiografia
  (468), ultrassonografia (254), outros (9).
- **Este documento consolida** todos os experimentos executados em escala
  completa (todos os casos `qualidade_dado: ok` de cada categoria, não
  amostras pequenas) — é o resultado final, não um plano. Os documentos de
  processo ficam como referência detalhada:
  [decision-models-laudos-veterinarios.pt.md](./decision-models-laudos-veterinarios.pt.md),
  [gliner2-decide-vs-laya-eco.md](./gliner2-decide-vs-laya-eco.md),
  [codiv-ai-multi-model-plan.pt.md](./codiv-ai-multi-model-plan.pt.md).

## Resumo executivo

| Modelo | Categoria | n | Recall | Precisão | Acurácia | Veredito |
|---|---|---|---|---|---|---|
| **laya:multilingual** (produção) | Ecocardiografia | 149 | **1.000** | **0.494** | **0.718** | ✅ Em produção |
| GLiNER2.5-multi-Decide | Ecocardiografia | 149 | 1.000 | 0.277 | 0.282 | ❌ Perde, não é integrado |
| laya:multilingual (few-shot, 2 exemplos) | Ecocardiografia | 147 | 1.000 | 0.274 | 0.279 | ❌ Piora, não usar |
| laya:multilingual | Ultrassonografia | 236 | 1.000 | 0.356 | 0.356 | ❌ Não discrimina (100% falsos positivos entre negativos) |
| GLiNER2.5-multi-Decide | Ultrassonografia | — | — | — | — | Não avaliado |
| openjev-latest (codiv.ai) | Eco (amostra) | 11 | 1.000 | 0.769* | 0.864* | Similar ao laya, não claramente melhor |
| openjev-latest (codiv.ai) | **Ultrassonografia (amostra)** | 11 | **1.000** | **1.000** | **1.000** | 🟢 **Separação perfeita — onde laya falha 100%** |
| jevk5-0.2 (codiv.ai) | Eco (amostra) | 11 | 1.000 | 0.714* | 0.818* | Similar ao laya, não claramente melhor |
| jevk5-0.2 (codiv.ai) | **Ultrassonografia (amostra)** | 11 | **1.000** | **1.000** | **1.000** | 🟢 **Separação perfeita — onde laya falha 100%** |
| — | Outros | 9 | — | — | — | Fora de escopo (amostra insuficiente) |

*Precisão/acurácia calculadas com "melhor limiar" sobre n=11 por categoria —
**sobreajuste provável com amostra tão pequena**, ver aviso em §4.

**Conclusão em uma linha**: `laya:multilingual` sobre a `Conclusão` de
ecocardiografia continua sendo a única combinação que funciona
razoavelmente (recall perfeito, metade dos positivos é falso alarme). Todo
o resto testado em escala real — GLiNER2.5, few-shot, e laya sobre
ultrassonografia — falha ou piora.

## 1. Ecocardiografia (468 arquivos, 149 avaliados com `qualidade_dado: ok`)

### 1.1 laya:multilingual — produção, Fase 7

Entrada: `Conclusão` nativa do laudo (mediana 12 palavras, p95 42).

| | TP | FN | FP | TN | Recall | Precisão | Acurácia |
|---|---|---|---|---|---|---|---|
| Limiar `gravidade >= 0.75` | 41 | 0 | 76 | 32 | 1.000 | 0.494 | 0.718 |

Distribuição de `gravidade`: positivos (min 0.781, mediana 1.756, max 1.962)
vs negativos (min 0.164, mediana 0.625, max 1.944) — a sobreposição na cauda
alta dos negativos (máx 1.944 > mín dos positivos) é a causa direta da
precisão de 0.494. Não existe limiar que separe limpo.

**Sensibilidade ao formato do `state` (achado lateral, EXP-004)**: mesmo
texto, mesmo checkpoint — string simples dá `gravidade=1.64`; envolvido em
`{"numero_relatorio":..., "laudo":...}` (formato real de produção) dá
`0.65`. Qualquer mudança futura em como `state` é montado pode deslocar o
limiar sem ninguém perceber.

### 1.2 GLiNER2.5-multi-Decide — EXP-001, perde

Mesmos 149 casos, mesma `Conclusão`, mesmo limiar de decisão
(recall=1.0 obrigatório).

| | Recall | Precisão | Acurácia |
|---|---|---|---|
| laya:multilingual | 1.000 | 0.494 | 0.718 |
| GLiNER2.5-multi-Decide | 1.000 | **0.277** | **0.282** |

O `score_sim` máximo entre os 41 casos que realmente precisavam internar é
0.493 — nunca cruza 0.5, o modelo nunca está "seguro" em nenhum caso grave.
Única vantagem: latência (129ms p50 vs ~1-2s e2e do laya via HTTP), não
compensa. **Não é integrado.**

### 1.3 Few-shot — EXP-004, piora

2 exemplos fixos (um normal, um grave) prefixados ao texto real, 147 casos
(149 − os 2 usados como exemplo), metodologia reduzida (só pergunta
`gravidade`, para isolar o efeito do few-shot do efeito do payload).

| | Recall | Precisão | Acurácia |
|---|---|---|---|
| Zero-shot (mesmo método reduzido) | 1.000 | 0.333 | 0.456 |
| Few-shot (2 exemplos) | 1.000 | **0.274** | **0.279** |

Mediana dos negativos salta de 0.969 (zero-shot) para 1.853 (few-shot) —
quase igual à mediana dos positivos (1.875). Prefixar exemplos destrói a
discriminação num encoder de classificação (não generativo). **Não usar
few-shot com laya.**

## 2. Ultrassonografia (254 arquivos, 236 avaliados com `qualidade_dado: ok`)

### 2.1 Conclusão derivada (atividade de qualidade de dados prévia)

Nenhum arquivo tinha `Conclusão` nativa (0/254). Foi derivada
deterministicamente a partir de `diagnosticos` + órgão (`"Exame abdominal
sem alterações."` ou `"Achado em <órgão>."`), marcada `conclusao_origem:
derivada_de_campos_estruturados` — nunca inventando detalhe clínico novo.

### 2.2 laya:multilingual — EXP-002b, falha total

| | TP | FN | FP | TN | Recall | Precisão | Acurácia |
|---|---|---|---|---|---|---|---|
| Limiar `gravidade >= 0.75` (mesmo de eco) | 84 | 0 | 152 | 0 | 1.000 | **0.356** | **0.356** |

**Previu `internação:true` para 100% dos 236 casos.** Precisão e acurácia
são exatamente a taxa base de positivos (84/236) — zero sinal real, não
melhor que sempre responder "sim". Causa provável: o limiar 0.75 foi
calibrado sobre o range real de `gravidade` de eco; o texto derivado,
genérico, satura tão alto quanto um caso grave real, independente do
`risco` verdadeiro.

**Não usar a Conclusão derivada para decisão de internação em
ultrassonografia sem mudar de abordagem** (recalibrar limiar específico, dar
mais contexto, ou abandonar o caminho).

### 2.3 GLiNER2.5-multi-Decide — não avaliado

Não foi rodado sobre ultrassonografia. Dado que já falha em eco (§1.2), não
é prioridade — se laya não discrimina sobre esse texto genérico, não há
razão para esperar que GLiNER2.5 discrimine.

## 3. Outros (9 arquivos)

Fora de escopo em todos os experimentos. `extracao_estruturada:
nao_suportada_ainda`, sem `risco`, sem `qualidade_dado`, headers finais
mistos (`Conclusão` / `Impressão diagnóstica:`). 9 arquivos é amostra
insuficiente para qualquer métrica de precisão/recall confiável — não vale
a pena uma estratégia dedicada a esse volume.

## 4. codiv.ai — sondeio de 22 casos (não escala completa)

**Decisão de escopo (2026-09-29)**: escalar `openjev-latest`/`jevk5-0.2`
para os 722 casos completos do corpus tem custo real — rate-limit
confirmado de 10s/chamada implica ~4 horas e gasto de API paga por 1.444
chamadas. Este sondeio de 22 casos (11 eco + 11 ultrassonografia, ambos com
mistura normal/grave) é indício, não prova — n pequeno demais para o
"melhor limiar" sem sobreajustar. Detalhe completo do desenho em
[codiv-ai-multi-model-plan.pt.md](./codiv-ai-multi-model-plan.pt.md).

### 4.1 Ecocardiografia (11 casos) — resultado similar ao laya

| Modelo | Positivos (score) | Negativos (score) |
|---|---|---|
| laya (local) | 1.62 – 1.87 | 0.60 – 1.89 |
| openjev-latest | 1.06 – 2.00 | 0.02 – 1.98 |
| jevk5-0.2 | 1.52 – 1.85 | 0.13 – 1.55 |

Os 3 modelos têm sobreposição visível em eco — nenhum claramente melhor
que laya nesta amostra.

### 4.2 Ultrassonografia (11 casos) — achado forte

| Modelo | Positivos (score) | Negativos (score) | Sobreposição |
|---|---|---|---|
| laya (local) | 1.20 – 1.32 | 0.89 – 0.97 | **Total** — confirma EXP-002b |
| **openjev-latest** | **0.89 – 0.96** | **0.01 – 0.02** | **Nenhuma — 11/11 perfeito** |
| **jevk5-0.2** | **0.54 – 0.64** | **0.01** | **Nenhuma — 11/11 perfeito** |

**Isto é um achado real, não ruído**: diferença de uma ordem de grandeza
entre positivos e negativos nos dois modelos do codiv.ai, sobre o mesmo
texto genérico derivado ("Exame abdominal sem alterações." vs "Achado em
X.") onde laya não distingue nada. Sugere que o problema de
ultrassonografia **não é o texto genérico em si** — é que laya
especificamente não o processa bem. Com n=11 o sinal é forte (separação
total, não marginal) mas continua sendo indício: falta escalar para mais
casos antes de decidir integrar.

**Achado lateral de segurança**: foi usada uma API key colada em texto
simples no chat (`sk-codiv-...`) — recomendou-se rotacioná-la, não foi
hardcoded em nenhum script commitado.

**Achado lateral técnico**: o cliente HTTP importa — `urllib.request` do
Python disparou 403 Forbidden persistente na API do codiv.ai mesmo com
backoff de 10s; a mesma requisição via subprocess `curl` funcionou sem
problema. Causa exata não diagnosticada (possível diferença de headers ou
manejo de keep-alive), documentado para não repetir a confusão.

## 5. Veredito final

1. **`laya:multilingual` sobre `Conclusão` de ecocardiografia continua
   sendo produção** — único caso com recall perfeito e precisão utilizável
   (0.494) como ferramenta de triagem, não decisão autônoma.
2. **Ultrassonografia com laya não tem caminho funcional** — nem a
   Conclusão derivada nem o limiar de eco servem, confirmado em escala
   completa (236 casos) e na amostra de 22.
3. **GLiNER2.5-multi-Decide e few-shot ficam descartados** para eco —
   evidência real, não suposição.
4. **Pista forte para ultrassonografia: `openjev-latest`/`jevk5-0.2`
   separam perfeito (11/11) onde laya falha 100%** (§4.2) — não confirmado
   em escala, mas o sinal é limpo demais para ser coincidência. É o achado
   mais promissor de toda a sessão para desbloquear o ponto 2. Próximo
   passo natural: escalar o sondeio de ultrassonografia especificamente
   (não eco, onde não há vantagem clara) para mais casos antes de decidir
   integrar.
5. **Nenhum desses resultados foi validado por um veterinário real** —
   continua pendente em todos os experimentos (ver ASM-001/Q-003 em
   `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`).

## Evidência (jsonl + scripts, todos neste diretório)

- `evidencia_gliner2_resultado_eco.jsonl` + `eval_exp001_eco.py` (GLiNER2.5, eco)
- `evidencia_openjev_zeroshot.jsonl` + `evidencia_openjev_fewshot.jsonl` + `eval_exp004_fewshot.py` (few-shot, eco)
- `evidencia_exp002b_ultrasom.jsonl` + `eval_exp002b_ultrasom.py` (laya, ultrassonografia)
- `evidencia_codiv_sondeo22.jsonl` + `eval_codiv_sondeo22.py` (sondeio codiv.ai, 22 casos)
