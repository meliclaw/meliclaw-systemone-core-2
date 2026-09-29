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
| **openjev-latest (codiv.ai)** | **Ecocardiografia (escala completa)** | **149** | **1.000** | **0.683** | **0.872** | 🟢 **Supera laya** |
| **openjev-latest (codiv.ai)** | **Ultrassonografia (escala completa)** | **236** | **1.000** | **1.000** | **1.000** | 🟢 **Separação perfeita, sem sobreposição** |
| jevk5-0.2 (codiv.ai) | Ecocardiografia (escala completa) | 149 | 1.000 | 0.651 | 0.852 | 🟢 Supera laya |
| **jevk5-0.2 (codiv.ai)** | **Ultrassonografia (escala completa)** | **236** | **1.000** | **1.000** | **1.000** | 🟢 **Separação perfeita, sem sobreposição** |
| — | Outros | 9 | — | — | — | Fora de escopo (amostra insuficiente) |

Todos os números do codiv.ai nesta tabela são sobre o corpus completo
(`qualidade_dado: ok`), não sondeio — ver §4.

**Conclusão em uma linha**: ao contrário do que o sondeio inicial de 11
casos sugeria ("sem vantagem clara"), em escala completa `openjev-latest`
**supera laya nas duas categorias** — não só em ultrassonografia. O n=11
não era representativo. GLiNER2.5 e few-shot com laya continuam
descartados.

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

**Atualização (§4.1): `openjev-latest` (codiv.ai) supera esse resultado
sobre os mesmos 149 casos** — acurácia 0.872 vs 0.718, precisão 0.683 vs
0.494, mesmo recall perfeito. laya deixa de ser a única opção com bom
desempenho em eco.

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

## 4. codiv.ai — escalado completo (eco 149 + ultrassonografia 236)

**Decisão de escopo (2026-09-29)**: escalar `openjev-latest`/`jevk5-0.2`
para eco + ultrassonografia completos tinha custo real — rate-limit de
10s/chamada, ~50min + ~79min de corridas pagas. Foi feito em duas passadas:
primeiro ultrassonografia (o sondeio de 11 mostrava separação perfeita), e
ao se confirmar, também eco — mesmo o sondeio de 11 em eco sugerindo "sem
vantagem clara", decidiu-se escalar igual para não confiar numa amostra tão
pequena. **A decisão de escalar eco foi correta: o sondeio de 11 estava
errado.**

### 4.1 Ecocardiografia — **escalado completo (149/149 casos, sem erros) — openjev supera laya**

| Modelo | Recall | Precisão | Acurácia | Positivos (score) | Negativos (score) |
|---|---|---|---|---|---|
| laya (local, produção) | 1.000 | 0.494 | 0.718 | 0.781 – 1.962 | 0.164 – 1.944 |
| **openjev-latest** | **1.000** | **0.683** | **0.872** | **1.001 – 1.999** | **0.003 – 1.995** |
| jevk5-0.2 | 1.000 | 0.651 | 0.852 | 0.748 – 1.855 | 0.119 – 1.564 |

O sondeio de 11 casos tinha sugerido "sem vantagem clara" — **estava
errado**. Em escala completa, `openjev-latest` melhora a acurácia do laya
em +0.154 e a precisão em +0.189 (menos falsos positivos, mesmo recall
perfeito). `jevk5-0.2` também melhora, um pouco menos.

Os ranges de score continuam se sobrepondo para os três modelos (diferente
da separação total vista em ultrassonografia) — a melhora vem de uma
distribuição interna melhor, não de uma separação limpa. É um resultado
mais "normal"/incremental que o de ultrassonografia, não um salto
qualitativo.

### 4.2 Ultrassonografia — **CONFIRMADO em escala completa (236/236 casos, sem erros)**

| Modelo | Recall | Precisão | Acurácia | Positivos (score) | Negativos (score) |
|---|---|---|---|---|---|
| laya (local, referência) | 1.000 | 0.457 | 0.576 | 0.886 – 1.417 | 0.785 – 0.977 |
| **openjev-latest** | **1.000** | **1.000** | **1.000** | **0.866 – 0.997** | **0.005 – 0.030** |
| **jevk5-0.2** | **1.000** | **1.000** | **1.000** | **0.422 – 0.941** | **0.011 (quase constante)** |

**Já não é indício — é resultado confirmado.** Sobre os 236 casos reais,
`openjev-latest` e `jevk5-0.2` separam com **precisão e acurácia perfeitas
(1.000)** — zero falsos positivos, zero falsos negativos. Margem entre
grupos: negativos do openjev nunca ultrapassam 0.030, positivos nunca
ficam abaixo de 0.866 — não há sobreposição em nenhum ponto dos 236 casos.
`jevk5-0.2` dá um score quase idêntico (~0.0106) para quase todos os
negativos — sugere que distingue de forma quase binária "Exame abdominal
sem alterações." (texto idêntico em 169/236 casos) de qualquer "Achado em
X."

laya melhorou levemente em relação ao EXP-002b (0.576 vs 0.356 de
acurácia) ao usar "melhor limiar" em vez do limiar fixo 0.75 de produção,
mas continua bem abaixo dos outros dois — seu range de positivos e
negativos se sobrepõe (positivo mín 0.886, negativo máx 0.977).

**Isso sugere fortemente que o problema de ultrassonografia não é o texto
genérico em si — é que laya especificamente não o processa bem.**
`openjev-latest`/`jevk5-0.2` distinguem esse mesmo texto de forma
praticamente perfeita.

**Ressalva metodológica, continua de pé**: o ground truth (`risco` no
frontmatter) é `rotulo_origem: proposto_por_ia` — proposto por uma regra
automática, não confirmado por um veterinário real. Uma separação perfeita
contra um rótulo também gerado por IA não é prova de acerto clínico, é
prova de que o modelo reproduz a mesma regra/padrão que gerou o rótulo.
Continua bloqueado por ASM-001/Q-003 antes de qualquer uso real.

**Achado lateral de segurança**: foi usada uma API key colada em texto
simples no chat (`sk-codiv-...`) — recomendou-se rotacioná-la, não foi
hardcoded em nenhum script commitado.

**Achado lateral técnico**: o cliente HTTP importa — `urllib.request` do
Python disparou 403 Forbidden persistente na API do codiv.ai mesmo com
backoff de 10s; a mesma requisição via subprocess `curl` funcionou sem
problema. Causa exata não diagnosticada (possível diferença de headers ou
manejo de keep-alive), documentado para não repetir a confusão.

## 5. Veredito final

1. **`openjev-latest` (codiv.ai) supera `laya:multilingual` nas DUAS
   categorias, confirmado em escala completa** — eco: acurácia 0.872 vs
   0.718 (149 casos, §4.1); ultrassonografia: acurácia 1.000 vs 0.356-0.576
   (236 casos, §4.2). O sondeio inicial de 11 casos em eco sugeria "sem
   vantagem" — estava errado; a decisão de escalar igual foi correta.
2. **laya:multilingual continua sendo a única coisa em produção hoje**,
   mas já não é a opção de melhor desempenho medido — é a opção com
   histórico (Fase 1-4, `vetsync-diagnostic`), não a de melhor resultado.
3. **GLiNER2.5-multi-Decide e few-shot com laya ficam descartados** para
   eco — evidência real, não suposição.
4. **Ultrassonografia com laya não tem caminho funcional** (§2.2) — mas
   `openjev-latest`/`jevk5-0.2` resolvem, com separação perfeita.
5. **Ressalva que se aplica a TUDO acima, não só a ultrassonografia**: o
   ground truth (`risco`) é `rotulo_origem: proposto_por_ia` nas duas
   categorias — nunca confirmado por um veterinário real. O
   `openjev-latest` prever melhor um rótulo gerado por IA não prova
   acerto clínico, prova que reproduz melhor o padrão que gerou esse
   rótulo. Isso se aplica igual aos números de eco que já estavam em
   produção (laya) — nunca foram validados também.
6. **Próximo passo real já não é mais sondeio/escalado** — é validação
   clínica por um veterinário (ASM-001/Q-003 em
   `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`),
   e avaliar migrar `vetsync-diagnostic` de laya para `openjev-latest`
   como backend, sujeito a essa validação e a confirmar custo/latência
   real da API do codiv.ai em produção (hoje só medido com rate-limit de
   sondeio, não com volume de tráfego real).

## Evidência (jsonl + scripts, todos neste diretório)

- `evidencia_gliner2_resultado_eco.jsonl` + `eval_exp001_eco.py` (GLiNER2.5, eco)
- `evidencia_openjev_zeroshot.jsonl` + `evidencia_openjev_fewshot.jsonl` + `eval_exp004_fewshot.py` (few-shot, eco)
- `evidencia_exp002b_ultrasom.jsonl` + `eval_exp002b_ultrasom.py` (laya, ultrassonografia)
- `evidencia_codiv_sondeo22.jsonl` + `eval_codiv_sondeo22.py` (sondeio codiv.ai, 22 casos, eco+ultrassom)
- `evidencia_codiv_ultrasom_236.jsonl` + `eval_codiv_ultrasom_236.py` (escalado completo, ultrassonografia, 236 casos)
- `evidencia_codiv_eco_149.jsonl` + `eval_codiv_eco_149.py` (escalado completo, ecocardiografia, 149 casos)
