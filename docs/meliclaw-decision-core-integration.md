# Meliclaw Decision Core Integration

## Objective

`meliclaw-systemone-core-2` exposes Ollaya as the System One decision service for `meliclaw-decision-core`.

It is intended for `meliclaw-router-core` decisions with the TypeSafe-compatible API:

- `choice`
- `noul`
- `score`

Primary endpoint:

```text
POST /v1/systemone
```

## macOS M1 Max Runtime

The target server is Mac OS X on Apple Silicon, so CUDA must not be used.

Ollaya's MLX engine uses Apple Metal through native macOS APIs. OrbStack containers are Linux containers and do not get direct access to Metal/MLX. Because of that, `meliclaw-systemone-core-2` is represented in OrbStack as a lightweight proxy container, while the real Ollaya daemon runs natively on macOS.

## Runtime Topology

```text
meliclaw-router-core
  -> http://meliclaw-systemone-core-2:11435/v1/systemone
  -> Docker proxy in meliclaw-decision-core
  -> host.docker.internal:11436
  -> native macOS Ollaya daemon using MLX/Metal
```

## Native Ollaya Setup

Run Ollaya natively on macOS:

```sh
export OLLAYA_DEVICE=metal
export OLLAYA_HOST=127.0.0.1:11436
ollaya serve
```

Pull the decision model:

```sh
ollaya pull laya
```

`laya` is a router model. It selects the appropriate Laya checkpoint, such as `laya:en` or `laya:multilingual`, depending on the request.

## Docker/OrbStack Service

`meliclaw-decision-core.yml` defines:

```text
meliclaw-systemone-core-2
```

The service listens on Docker internal port `11435` and proxies to native macOS Ollaya at:

```text
host.docker.internal:11436
```

Host port:

```text
127.0.0.1:18135 -> 11435
```

The host port can be overridden with:

```sh
MELICLAW_SYSTEMONE_CORE_2_HOST_PORT=18135
```

## Router Wiring

`meliclaw-router-core` receives these defaults:

```text
MELICLAW_SYSTEMONE_BASE_URL=http://meliclaw-systemone-core-2:11435
MELICLAW_SYSTEMONE_SYSTEMONE_URL=http://meliclaw-systemone-core-2:11435/v1/systemone
MELICLAW_SYSTEMONE_MODEL=laya:latest
MELICLAW_SYSTEMONE_DECISION_TYPES=choice,noul,score
```

## Verification

From macOS:

```sh
curl -fsS http://127.0.0.1:11436/
curl -fsS http://127.0.0.1:11436/v1/models
```

From the Docker proxy:

```sh
curl -fsS http://127.0.0.1:18135/v1/models
```

Smoke decision:

```sh
curl -fsS http://127.0.0.1:18135/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "laya:latest",
    "state": "Customer says they were charged twice this month.",
    "questions": {
      "is_billing": {
        "type": "noul",
        "instructions": "Is this a billing issue?"
      }
    }
  }'
```

Expected response shape:

```json
{
  "model": "laya:latest",
  "answers": {
    "is_billing": {
      "type": "noul",
      "noul": 0.0
    }
  },
  "usage": {}
}
```

The probability value is model-dependent.

## Operational Notes

- Do not use CUDA on this host.
- Do not use the upstream Ollaya CUDA Docker image for this service.
- Port `11435` may already be used by Ollama. Use native Ollaya on `11436`; the Docker proxy still exposes internal port `11435` for Meliclaw services.
- If native Ollaya is stopped, the proxy container becomes unhealthy.
- If `meliclaw-router-core` is already running under another Compose project, recreate it deliberately before expecting the new `MELICLAW_SYSTEMONE_*` environment defaults to apply.
