<p align="center">
  <img src="site/public/static/logo-meliclaw.png" alt="" width="88">
</p>

<h1 align="center">Meliclaw System One Core 2</h1>

<p align="center"><strong>Rode modelos de decisão abertos localmente, do mesmo jeito que o Ollama roda LLMs.</strong></p>

<p align="center">
  <a href="https://ollaya.dev">Website</a> ·
  <a href="https://ollaya.dev/search">Models</a> ·
  <a href="https://ollaya.dev/docs">Docs</a> ·
  <a href="https://github.com/ollaya-dev/ollaya/releases">Releases</a> ·
  <a href="https://huggingface.co/ollaya-dev">Hugging Face</a>
</p>

Um modelo de decisão lê um *state* (uma mensagem, um e-mail, um ticket, qualquer JSON) mais
perguntas tipadas (`choice`, `score`, `noul`) e devolve probabilidades calibradas num único forward
pass, em milissegundos. Nunca gera texto. Meliclaw System One Core 2 baixa esses modelos por nome,
serve a partir de um daemon local, e fala o formato de rede `/v1/systemone` do TypeSafe, então
clientes Jev existentes funcionam trocando uma variável de ambiente.

```sh
curl -fsSL https://ollaya.dev/install.sh | sh
ollaya run winnow:e4b --preset triage "Third time this year you've double-charged me. Refund it today or I'm cancelling and moving to a competitor."
```

```
intent            refund                                ███████████████░ 0.91
is_urgent         yes                                   ███████████████░ 0.92
frustration       2.89 / 3  very angry or using stron…  ██████████████░░ 0.86
refund_requested  yes                                   ████████████████ 0.99
churn_risk        yes                                   ████████████████ 0.99
```

`winnow:e4b` é o modelo recomendado: 0.722 de acurácia em decisões tipadas (Jev do TypeSafe: 0.738)
e 89 ms para essas cinco perguntas numa RTX 4090. É um modelo de linguagem classe 4B, então sem GPU
NVIDIA comece com `laya`, que responde numa fração de segundo em CPU. Todos os modelos e seus
números: [ollaya.dev/search](https://ollaya.dev/search).

## Recursos

- **Um binário.** `ollaya serve` roda o daemon; `ollaya run`, `pull`, `list`, `ps`, `show`, `rm`,
  `cp`, `stop` e `create` funcionam do mesmo jeito que no Ollama. Se o daemon não estiver rodando, a
  CLI o inicia.
- **Compatível com TypeSafe.** `POST /v1/systemone`, `/v1/decisions` e `GET /v1/models` são
  idênticos ao TypeSafe na rede. O SDK oficial funciona sem mudanças quando você define
  `TYPESAFE_BASE_URL=http://localhost:11435`.
- **API nativa.** `/api/decide` adiciona informação de roteamento e tempos. `/api/pull` transmite
  progresso NDJSON, e há `/api/tags`, `/api/show`, `/api/ps` e mais. Ver
  [docs/api.md](docs/api.md).
- **Pesos vêm dos próprios autores.** Meliclaw System One Core 2 publica só pequenos grafos ONNX,
  uns 3 MB cada. Esses grafos leem os arquivos de peso originais (geralmente
  `model.safetensors`) do repositório Hugging Face do autor, fixado num commit e verificado por
  sha256. Modelos cujos autores publicam arquivos GGUF (`winnow`, `jevk5`) rodam esse arquivo
  diretamente no llama.cpp. Meliclaw System One Core 2 nunca re-hospeda pesos.
- **Para agentes.** `ollaya mcp` serve os modelos para Claude Code, Claude Desktop, Cursor e outros
  clientes MCP (`claude mcp add ollaya -- ollaya mcp`), e a
  [skill `ollaya-decisions`](skills/ollaya-decisions/SKILL.md) ensina agentes quando e como usá-los
  (`npx skills add ollaya-dev/ollaya --skill ollaya-decisions`).
- **Roteadores.** `laya` detecta o script e o idioma de cada requisição, depois responde com
  `laya:en` ou `laya:multilingual`.
- **Modelfiles.** Você pode embutir um conjunto de perguntas no seu próprio modelo:
  ```
  FROM laya
  QUESTIONS ./triage.json
  PARAMETER precision fp32
  ```
  Depois rode `ollaya create triage -f Modelfile` e `ollaya run triage "…"`.
- **Rápido e exato.**
  - **Hardware:** ONNX Runtime em CPU, e CUDA em GPUs NVIDIA. Modelos GGUF rodam no llama.cpp:
    CPU, CUDA, e Metal em Apple silicon.
  - **Precisão:** fp16 na GPU e fp32 na CPU, escolhido quando o modelo carrega.
  - **Acurácia:** exports fp32 dão a mesma decisão que a referência PyTorch em 100% de 2.383
    perguntas por checkpoint.

## Modelos

| Modelo | O que é |
|---|---|
| `winnow:e4b` | **Recomendado.** Winnow-E4B de EldanRing, um fine-tune do Gemma 4 rodado a partir do GGUF Q8_0 do autor no llama.cpp: 0.722 em decisões tipadas (Jev: 0.738), 89 ms para cinco perguntas numa RTX 4090 |
| `laya` | Roteador: escolhe `laya:en` ou `laya:multilingual` pelo idioma |
| `laya:en` | Modelo de decisão em inglês (ModernBERT-large, 421M). O mais rápido: 8–10 ms para cinco perguntas numa RTX 4090 |
| `laya:multilingual` | 100+ idiomas (mmBERT-base, 322M) |
| `laya:typed-decisions` | Fine-tuned nos fluxos de decisões tipadas |
| `decider`, `decider:4b`, `decider:0.8b` | Decoders Qwen3.5 de Mapika, 2B (padrão), 4B e 0.8B: 0.680 em decisões tipadas para o 4B, 0.591 para o 2B |
| `decider:2b-vision` | Decider Qwen3.5-2B vision-language de Mapika: perguntas sobre uma imagem (`--image`, `images` em `/api/decide`) além do state |
| `kev`, `kev:0.8b`, `kev:9b` | Kev de Jared Palmer: uma LoRA e uma pointer head sobre Qwen3.5 (4B por padrão, 0.8B, 9B), calibrado. `kev:4b` marca 0.669 em decisões tipadas e `kev:9b` 0.722, tanto quanto `winnow:e4b` |
| `decision` | Decision 1.0 Eos dos contribuidores do vLLM Semantic Router: um Qwen3.5-0.8B fine-tuned com endpoint head, linhas de 16k tokens |
| `qwen3guard` | Guarda de segurança Qwen3Guard-Gen-0.6B com perguntas embutidas: seguro, controverso ou inseguro, e a categoria |
| `nli`, `nli:modernbert-large` | Classificadores NLI zero-shot de Moritz Laurer (DeBERTa-v3-large, ModernBERT-large) |
| `gliclass` | Classificador zero-shot com instruções de Knowledgator (DeBERTa-v3-large) |
| `von` | Von 1.1 de Victor Hugo Panisa (ModernBERT-large): cada opção pontuada no seu próprio marcador, contexto de 8k tokens |
| `winnow` | Winnow-12B de EldanRing, o irmão maior do `winnow:e4b`: 0.702 em decisões tipadas |
| `clm` | CLM-v0.1-8B de Contrastive-LM: o encoder Qwen3-8B e duas projection heads pontuam opções por similaridade, com perguntas e opções em cache. 0.357 em decisões tipadas; feito para states de agente, jogo e tool-calling |
| `jevk5` | JevK5 v0.3 de alibiserikbay, um fine-tune Qwen3.5-4B rodado a partir do GGUF Q8_0 do autor no llama.cpp, até 16 opções |

Navegue por eles em [ollaya.dev/search](https://ollaya.dev/search). Tags de laya terminando em
`-fp32` ou `-fp16` fixam a precisão. Os arquivos derivados de todo modelo também são publicados em
[huggingface.co/ollaya-dev](https://huggingface.co/ollaya-dev).

## Instalação

- **Linux** (x86_64 ou arm64, glibc ≥ 2.38, ex. Ubuntu 24.04+):
  `curl -fsSL https://ollaya.dev/install.sh | sh`. Quando há GPU NVIDIA presente
  (driver R525+), o instalador adiciona o runtime CUDA: CUDA 13 para R580+, CUDA 12 para drivers
  mais antigos.
- **macOS** (Apple silicon): o mesmo comando.
- **Windows** (x64): `irm https://ollaya.dev/install.ps1 | iex` no PowerShell. Quando há GPU NVIDIA
  presente (driver R527+), o instalador adiciona o runtime CUDA, como no Linux.
- **App desktop** para macOS, Windows e Linux: inicia e para o servidor, baixa modelos e roda eles
  numa janela só. No macOS fica na barra de menu. Pegue em
  [ollaya.dev/download](https://ollaya.dev/download).
- **Docker:** `docker run -d --gpus=all -p 11435:11435 ghcr.io/ollaya-dev/ollaya:cuda`
  (`:cuda12` para drivers de host mais antigos que R580), ou `ghcr.io/ollaya-dev/ollaya` só para CPU.

Configuração é via variáveis de ambiente: `OLLAYA_HOST`, `OLLAYA_MODELS`,
`OLLAYA_KEEP_ALIVE`, `OLLAYA_DEVICE`, `OLLAYA_API_KEY` e outras, listadas em
[docs/api.md §15](docs/api.md).

## Repositório

| Caminho | O que é |
|---|---|
| `crates/ollaya` | O binário: CLI, daemon, runner |
| `crates/ollaya-server` | API HTTP, scheduler (um processo runner por modelo), resolução de modelo |
| `crates/ollaya-api` | Tipos de API e client; o contrato é [docs/api.md](docs/api.md) |
| `crates/ollaya-registry` | Nomes de modelo, manifests, blob store, pulls retomáveis |
| `crates/ollaya-decision` | Schema de perguntas, layouts de sequência, calibração, respostas |
| `crates/ollaya-runner` | Engines de inferência (ONNX Runtime, e llama.cpp para modelos GGUF) |
| `crates/ollaya-lang` | Detecção de script e idioma para roteadores |
| `convert/` | Python de build-time: export ONNX, checagem de paridade, empacotamento |
| `site/` | O site e o host estático do registro de modelos |

## Desenvolvimento

```sh
cargo test --workspace
cargo build --release -p ollaya --features cuda   # build CUDA (x86-64 Linux e Windows)
```

`convert/` reconstrói modelos. Exporta eles, checa paridade contra a referência PyTorch, gera
fixtures golden, e empacota o resultado em `registry/`. Ver os docstrings dos módulos.
`cd convert && uv sync` instala: com torch CUDA 13 no Linux e Windows, e com o build de CPU e MPS
do PyPI em Macs Apple silicon, onde exports e paridade rodam na CPU.

## Licença

Apache-2.0. Cada modelo mantém sua própria licença: `laya` (Convai Innovations), `decider`
(Mapika), `kev` (Jared Palmer, sobre Qwen3.5 do time Qwen), `decision` (contribuidores do vLLM
Semantic Router, sobre Qwen3.5), `qwen3guard` (time Qwen), `gliclass` (Knowledgator), `von` (Victor
Hugo Panisa), `winnow` (EldanRing, sobre Gemma 4 do Google DeepMind), `jevk5` (alibiserikbay, sobre
Qwen3.5) e `nli:modernbert-large` são Apache-2.0, e `nli:deberta-v3-large` (Moritz Laurer) é MIT.
llama.cpp, que Meliclaw System One Core 2 embarca para modelos GGUF, é MIT.

Meliclaw System One Core 2 é um repositório fork do Ollaya e um projeto independente. Não é afiliado nem endossado por Ollama ou TypeSafe.
