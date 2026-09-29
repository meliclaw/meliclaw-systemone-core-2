# Documento técnico: modelos de decisão tipada sobre laudos veterinários

- **Estado:** técnico/funcional, vivo — reflete o medido até 2026-09-29.
- **Escopo:** as 3 categorias do corpus `dataset/vet/train/`: ecocardiografia
  (468), ultrassonografia (254), outros (9).
- **Relacionado:** [gliner2-decide-vs-laya-eco.md](./gliner2-decide-vs-laya-eco.md)
  (experimento go/no-go, só eco); `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/`
  (feature em produção, só eco).

---

## 1. Os modelos

### 1.1 laya:multilingual (em produção)

| Campo | Valor |
|---|---|
| Encoder | mmBERT-base |
| Parâmetros | 322M |
| Janela de contexto | **1.024 tokens** |
| Formato servido | ONNX (F16), via Ollaya |
| Calibração | **Sim** — o próprio catálogo do Ollaya marca `calibrated` |
| Endpoint | `POST /v1/systemone` (compatível TypeSafe), `meliclaw-systemone-core-2` |
| Capacidades | `choice`, `score`, `noul` (decisões tipadas, um forward pass) |
| Licença/origem | `huggingface.co/convaiinnovations/laya` |

Fonte: `meliclaw-systemone-core-2/docs/api.md` (specs verificadas contra a API real).

### 1.2 GLiNER2.5-multi-Decide (em avaliação, não integrado)

| Campo | Valor |
|---|---|
| Encoder | mDeBERTa-v2/v3-base (hidden=768, 12 camadas) |
| Parâmetros | 287.4M (confirmado via API do Hugging Face, não o marketing) |
| Janela de contexto | **512 tokens** |
| Arquitetura | `BoundaryExtractor` (propose-then-rerank span extraction — **não** um MLP simples sobre marcadores) |
| Formato servido | Biblioteca `gliner2` (Python, CPU-first, não exige GPU) |
| Calibração | **Não** — `temperature=1.0, threshold=0.5` sem calibrar (declarado pelo próprio fornecedor) |
| Endpoint | `AutoExtractor.from_pretrained(...)`, local, sem servidor HTTP próprio |
| Licença/origem | Apache-2.0, `fastino/GLiNER2.5-multi-Decide` @ base `fastino/gliner2.5-multi-v1` |

**Nota de correção**: o modelo `fastino/GLiNER2.5-Decide` (340M, DeBERTa-v3-large) é **só inglês** — não serve para este corpus (PT-BR). A variante correta é `-multi-Decide`.

### 1.3 Comparação direta

| | laya:multilingual | GLiNER2.5-multi-Decide |
|---|---|---|
| Contexto | 1.024 tokens | 512 tokens |
| Parâmetros | 322M | 287.4M |
| Calibrado | Sim | Não |
| Benchmark do fornecedor (`fast-decisions`, genérico, não é nosso domínio) | Laya Router: 46.6% | 56.7% |
| Validado no nosso domínio (eco, 149 casos reais) | Sim — recall=1.000, precisão=0.494, acurácia=0.718 | Não — pendente (ver experimento) |

---

## 2. Formatos de arquivo de entrada, por categoria

Todos os arquivos são Markdown com frontmatter YAML + corpo de texto livre em
PT-BR. Pasta `old/` de cada categoria **sempre é ignorada** (duplicados
obsoletos).

### 2.1 Ecocardiografia (468 arquivos)

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
# ... campos clínicos estruturados (medidas, achados) ...
padrao_diastolico: restritivo
insuf_mitral: nenhuma
diagnosticos: [disfuncao_diastolica_restritiva]
risco: moderado          # baixo | baixo_moderado | moderado
qualidade_dado: revisar  # ok | revisar
---

Numero de relatorios: ...
Conteúdo

[seções: Ventrículo Esquerdo, Ventrículo Direito, Valvas, Pericárdio,
Avaliação da função diastólica, Avaliação hemodinâmica — com medidas,
muitas vezes vazias/`null`]

Conclusão

[1-3 frases, o veredito clínico condensado]
```

- **Tem seção `Conclusão` em 100% dos casos** (verificado).
- `qualidade_dado: ok` em 149/468 (32%); `revisar` em 319/468 (68%) — maioria
  com campos numéricos vazios no frontmatter, como o exemplo acima.
- Comprimento real da `Conclusão` (149 casos `ok`, medido): mediana 12
  palavras, p95 42, máximo 49 — bem abaixo de qualquer limite de contexto.

### 2.2 Ultrassonografia (254 arquivos)

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
risco: baixo              # baixo | moderado (não há baixo_moderado nesta categoria)
qualidade_dado: ok
---

Conteúdo

Fígado – de dimensões preservadas...
Vesícula biliar - ...
Baço - ... (Achados relacionados com esplenomegalia...)
Estômago – ...
Alças intestinais - ...
Rins – ...
[... órgão por órgão ...]
Aorta e veia cava caudal com trajeto preservado.
```

- ~~**`Conclusão` NÃO existe em NENHUM arquivo (0/254, verificado)**~~ —
  **resolvido em 2026-09-29** (ver §6 abaixo): os 254 arquivos agora têm
  `Conclusão` derivada de `diagnosticos` + órgão, marcada explicitamente
  `conclusao_origem: derivada_de_campos_estruturados` no frontmatter — não é
  texto do veterinário original, é reformatação determinística de campos que
  já estavam estruturados no mesmo arquivo. Script:
  `meliclaw-systemone-core-2/convert/ollaya_convert/families/gliner2/derive_conclusao_ultrasom.py`.
- `qualidade_dado: ok` em 236/254 (93%) — proporção bem melhor que eco.
- `risco`: só `baixo`/`moderado` (2 níveis, não 3 como em eco).
- **Implicação (resolvida)**: a estratégia "mandar só a `Conclusão`" (usada em
  eco) agora se aplica também aqui — ver §6, atividade de qualidade de dados.

### 2.3 Outros (9 arquivos)

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

- `extracao_estruturada: nao_suportada_ainda` — sem campos clínicos
  estruturados, sem `risco`, sem `qualidade_dado`. Categoria catch-all.
- Header final **misto**: alguns usam `Conclusão`, outros `Impressão
  diagnóstica:` — sem padrão único.
- **Fora do escopo atual** — nem a feature de eco nem o experimento GLiNER2.5
  tocam nisso. 9 arquivos é amostra insuficiente para qualquer medição de
  precisão/recall confiável.

---

## 3. Método: prompting / few-shot — não fine-tuning

**Não há treinamento em nenhum ponto deste trabalho.** laya e GLiNER2.5 são
modelos já pré-treinados por terceiros (convaiinnovations, fastino). O único
que fazemos é *inferência com perguntas tipadas* — passar texto + um esquema
de perguntas em cada chamada, sem tocar em nenhum peso do modelo.

### 3.1 Decisões tipadas (laya, padrão `/v1/systemone`)

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

Um forward pass, sem geração de tokens. Resposta: probabilidade calibrada por
pergunta (`noul` = sim/não, `score` = nível ordinal, `choice` = categoria com
confiança). Isso é "prompting" no sentido de: o desenho do texto de
`instructions`/`criteria` é a única coisa que se ajusta — nunca os pesos.

### 3.2 Few-shot (onde entraria, se fosse preciso)

Nem laya nem GLiNER2.5 usam exemplos no prompt na implementação atual
(zero-shot puro: só instruções, sem exemplos resolvidos). Few-shot de verdade
significaria incluir 1-3 casos já resolvidos como contexto em `state` —
**não foi feito em nenhum experimento até agora**, é uma alavanca sem testar,
não uma técnica já aplicada. Se a precisão não melhorar só com calibração de
limiar, é o próximo experimento razoável, não fine-tuning.

### 3.3 Por que não fine-tuning

- Custo: exige GPU dedicada, pipeline de treinamento, dataset rotulado por
  veterinário real (não temos — ver ASM-001/Q-003 em
  `vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`). Sem
  ground truth clínico confiável, treinar é ajustar contra ruído.
- laya e GLiNER2.5-multi-Decide já são modelos *fine-tuneados* pelo fornecedor
  para a tarefa de "decisão tipada" em geral — a pergunta não é se o modelo
  sabe fazer o tipo de tarefa, é se o *prompt específico* (`instructions`,
  `criteria`, qual texto de entrada) está bem desenhado para o nosso domínio.
  Isso se resolve com prompting, não com treinamento.

---

## 4. Métricas medidas — ecocardiografia, laya:multilingual (Fase 7)

Único resultado com dados reais até agora. Corpus: 149 casos `qualidade_dado:
ok`, ground truth = `risco == moderado` → `internacao` esperada `true`.

| Entrada | Erros de chamada | Recall | Precisão | Acurácia |
|---|---|---|---|---|
| Laudo completo (sem extração) | 39/149 (26%) — `STATE_TRUNCATED` | — | — | 0.118 (previu `internação` para 100%) |
| Só `Conclusão` | 0/149 | **1.000** | 0.494 | 0.718 |

Distribuição real de `gravidade` (score 0-2) sobre `Conclusão`:

| Grupo | n | min | p25 | mediana | p75 | max |
|---|---|---|---|---|---|---|
| Esperado internar (risco=moderado) | 41 | 0.781 | 1.623 | 1.756 | 1.823 | 1.962 |
| Esperado não internar | 108 | 0.164 | 0.553 | 0.625 | 1.470 | 1.944 |

Limiar usado em produção: `gravidade >= 0.75` (garante recall=1.000 —
prioridade clínica: nunca perder um caso real). A sobreposição entre grupos
(negativo máx 1.944 > positivo mín 0.781) é a causa direta da precisão baixa
(0.494) — não há limiar que separe limpo.

---

## 5. (número reservado — sem conteúdo próprio; ver §6 e §7)

---

## 6. Atividade de qualidade de dados — Conclusão derivada para ultrassonografia (2026-09-29)

Resolve o que era EXP-002 (estado anterior deste documento). Registro do que
foi feito, para rastreabilidade.

### 6.1 Problema

Nenhum dos 254 laudos de ultrassonografia tinha seção `Conclusão` (0/254,
verificado por grep). O laudo terminava direto no achado do último órgão
avaliado. A estratégia que funciona em eco ("mandar só a Conclusão",
recall=1.000/precisão=0.494 medido) não tinha o que extrair aqui.

### 6.2 Opções descartadas

- **Laudo completo**: já sabemos por eco que satura o sinal do modelo (0% de
  discriminação, 26% de falhas por contexto) — descartada sem testar de novo,
  a causa raiz (ruído + comprimento) é a mesma em ultrassonografia.
- **Gerar a Conclusão com um LLM** (eu redigindo um resumo por arquivo):
  descartada — fabricaria conteúdo clínico que o veterinário nunca escreveu,
  contaminando o dataset de avaliação. Teria custado ~150-200k tokens
  adicionais sem necessidade.
- **Citar o texto livre `<orgao>_achado` do frontmatter**: testado primeiro,
  descartado ao ver o resultado — esse campo já vem truncado na fonte (corta
  no meio de uma palavra, ex. `"...com presença de áre"` em
  `REL-20260407-018.md`). Pegar a "primeira frase" dali produzia frases
  falsamente completas e enganosas (ver commit de teste, revertido antes de
  aplicar).

### 6.3 Solução aplicada — derivação por regras, sem texto livre

Script `meliclaw-systemone-core-2/convert/ollaya_convert/families/gliner2/derive_conclusao_ultrasom.py`:
deriva a Conclusão **só** do campo `diagnosticos` (códigos já estruturados,
confiáveis) + nome do órgão — nunca do texto livre truncado.

```python
# regra completa (simplificada):
if diagnosticos == ["exame_abdominal_sem_alteracoes"]:
    return "Exame abdominal sem alterações."
# senão, um órgão por código de diagnóstico (achado_renal → "rins", etc.)
return f"Achado em {orgao}. Ver seção correspondente no corpo do laudo para detalhes."
# (ou "Achados em X e Y..." se houver mais de um órgão)
```

Cada arquivo modificado ganha `conclusao_origem: derivada_de_campos_estruturados`
no frontmatter — transparência explícita de que não é texto do veterinário
original.

### 6.4 Resultado, verificado

- 254/254 arquivos com `Conclusão` (antes: 0/254).
- 254/254 com `conclusao_origem` marcado.
- 254/254 com frontmatter YAML válido (verificado por parsing, não só grep).
- Distribuição das 254 conclusões geradas:

| Conclusão derivada | n |
|---|---|
| "Exame abdominal sem alterações." | 169 |
| Achado em rins | 23 |
| Achado em vesícula urinária | 19 |
| Achados em rins e vesícula urinária | 16 |
| Achado em fígado | 9 |
| Achados em fígado e rins | 6 |
| Achado em pâncreas | 5 |
| (combinações de 3 órgãos) | 6 |

- Validado em 2 arquivos de teste (cópia, não o original) antes de aplicar aos
  254 reais.
- Commit: `0f08cd5d` em `agentic-platform` (branch
  `fix/vetsync-diagnostic-rustls-cross-compile`, não enviado ao remoto). 254
  arquivos, 17.989 inserções — eram arquivos não rastreados no git até este
  commit.

### 6.5 O que isso NÃO resolve

- A qualidade clínica do texto derivado não foi revisada por um veterinário —
  mesmo tipo de ressalva que ASM-001 na feature de eco. "Achado em rins" é
  deliberadamente genérico (não inventa gravidade nem detalhe), mas continua
  sendo uma reformulação automática, não um julgamento clínico.
- Não valida que o modelo (laya ou GLiNER2.5) tenha bom desempenho sobre esse
  texto derivado — isso é o EXP-002b, trabalho novo, ainda não feito.

---

## 7. Perguntas em aberto / próximos passos

| ID | Pergunta | Bloqueia |
|---|---|---|
| EXP-001 | GLiNER2.5-multi-Decide sobre os mesmos 149 casos de eco — ganha do laya em precisão, mantendo recall=1.000? | Ver `gliner2-decide-vs-laya-eco.md`, Fase 1, não executada |
| EXP-002b | Com a Conclusão derivada (§6) já disponível nos 254 de ultrassonografia, laya (ou GLiNER2.5) discrimina bem `risco: baixo` vs `moderado` sobre esse texto genérico ("Achado em rins.")? Não medido — o texto derivado é deliberadamente pobre em detalhe, pode não bastar para discriminar | Bloqueia qualquer feature de decisão sobre ultrassonografia — não começado |
| EXP-003 | Outros (9 casos, headers mistos) — vale a pena uma estratégia dedicada para 9 arquivos, ou se descarta a categoria? | Não começado, provavelmente descartável por volume |
| EXP-004 | Few-shot (§3.2) sem testar — se EXP-001 não melhorar a precisão, o próximo passo é few-shot ou coletar ground truth clínico real? | Depende do resultado de EXP-001 |

Todas as perguntas ASM/Q da feature de eco em produção
(`vetsync-diagnostic/.spec/features/diagnostico-internacao-eco/spec.md`)
continuam abertas e não são repetidas aqui.
