# Halo API v2 - Guía de Uso

## Resumen

La API v2 usa la arquitectura policy-driven con context levels, permitiendo que Halo se manifieste como Home o Care sin cambiar código.

## Endpoints

### Legacy (v1)
```
POST /command              # ClassifierChain original
GET /health               # Health check
GET /classifier-chain     # Info de la cadena
```

### Nueva (v2)
```
POST /v2/command          # PolicyDrivenChain con context levels
GET /v2/health           # Health check v2
GET /v2/info             # Info del dominio y soul
GET /v2/soul             # Manifest completo
GET /v2/context          # Contexto completo (5 niveles)
GET /v2/logs/telemetry   # Logs de telemetría
```

## Configuración

### Elegir Dominio

Usa la variable de entorno `HALO_DOMAIN`:

```bash
# Halo Home
export HALO_DOMAIN=home
make server

# Halo Care
export HALO_DOMAIN=care
make server
```

## Ejemplos de Uso

### 1. Iniciar Halo Home

```bash
# Terminal 1: Start server
export HALO_DOMAIN=home
make server

# Terminal 2: Test
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{
    "message": "enciende la luz del salon",
    "context": {"user": "ernesto"}
  }'
```

Respuesta:
```json
{
  "result": {
    "status": "completed",
    "message": "Luz de sala encendida",
    "device_state": {"power": "on", "room": "sala"}
  },
  "context": {
    "session_id": "session_1773115892.456",
    "last_room": "sala"
  }
}
```

### 2. Iniciar Halo Care

```bash
# Terminal 1: Start server
export HALO_DOMAIN=care
make server

# Terminal 2: Test
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Roberto se levantó",
    "context": {
      "operator": "carla",
      "operator_fatigue": 0.72,
      "alert_level": "active"
    }
  }'
```

### 3. Ver el Manifest (Alma)

```bash
curl http://localhost:8000/v2/soul | jq .
```

Respuesta (Home):
```json
{
  "manifest": "# Halo Home - Casa de Ernesto\n\n## Quién Soy\nSoy el asistente de hogar de Ernesto...",
  "personality": {
    "voice": {
      "tone": "directo",
      "style": "informal pero respetuoso"
    },
    "schedule": {
      "active_hours": {"start": "07:00", "end": "23:00"}
    }
  },
  "relationships": {},
  "trust_score": 0.0,
  "days_active": 0
}
```

### 4. Ver Contexto Completo (5 Niveles)

```bash
curl http://localhost:8000/v2/context | jq .
```

Respuesta:
```json
{
  "manifest": "# Halo Home...",
  "personality": {...},
  "time_of_day": "morning",
  "current_state": {...},
  "operator_fatigue": 0.0,
  "alert_level": "calm",
  "session_id": "session_123",
  "user_or_operator": "ernesto",
  "interaction_count": 3,
  "conversation_history": [...]
}
```

### 5. Ver Telemetría

```bash
curl "http://localhost:8000/v2/logs/telemetry" | jq .
```

Respuesta:
```json
{
  "date": "today",
  "count": 5,
  "logs": [
    {
      "ts": "2024-03-10T10:15:00",
      "stage": "exact_match",
      "confidence": 0.0,
      "latency_ms": 0.1,
      "tokens": 0,
      "result_tool": null
    },
    {
      "ts": "2024-03-10T10:15:00",
      "stage": "keyword",
      "confidence": 0.90,
      "latency_ms": 0.3,
      "tokens": 0,
      "result_tool": "light_control"
    }
  ]
}
```

### 6. Ver Info del Sistema

```bash
curl http://localhost:8000/v2/info | jq .
```

Respuesta:
```json
{
  "domain": "home",
  "name": "Halo Home",
  "policy": "ThresholdPolicy",
  "classifiers": ["exact_match", "keyword", "llm"],
  "interceptors": ["TelemetryInterceptor", "LearningInterceptor", "ClassificationLogInterceptor"],
  "soul": {
    "manifest_preview": "# Halo Home - Casa de Ernesto\n\n## Quién Soy\nSoy el asistente de hogar de Ernesto. Mi trabajo es hacer su casa más cómoda sin ser intrusivo...",
    "relationships": [],
    "trust_score": 0.0
  },
  "sessions_active": 1
}
```

## Sesiones

La v2 API maneja sesiones automáticamente:

```bash
# Primera interacción (crea sesión)
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{"message": "enciende la luz", "context": {"user": "ernesto"}}'

# Respuesta incluye session_id
# "context": {"session_id": "session_123"}

# Segunda interacción (usa contexto de sesión)
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{"message": "apagala", "context": {"session_id": "session_123"}}'

# Contexto se mantiene - infiere que "apagala" = apagar luz de sala
```

## Comparación v1 vs v2

| Aspecto | v1 (Legacy) | v2 (Policy-Driven) |
|---------|-------------|---------------------|
| **Chain** | ClassifierChain | PolicyDrivenChain |
| **Policy** | Hardcoded thresholds | Configurable (Threshold/Care) |
| **Context** | Dict simple | HaloContext (5 niveles) |
| **Observability** | Logs básicos | Interceptors + JSONL |
| **Storage** | In-memory | File-based store |
| **Soul** | No | Sí (manifest.md) |
| **Domain** | Hardcoded home | Configurable (home/care) |
| **Agnostic** | No | Sí |

## Testing

### Test Rápido

```bash
# Start server con domain
export HALO_DOMAIN=home
make server

# En otra terminal
./test_v2_api.sh
```

### Test Manual

```bash
# Health check
curl http://localhost:8000/v2/health

# Info
curl http://localhost:8000/v2/info | jq .

# Soul
curl http://localhost:8000/v2/soul | jq .manifest

# Command
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{"message": "enciende la luz del salon"}'

# Telemetry
curl http://localhost:8000/v2/logs/telemetry | jq .
```

## Migrando de v1 a v2

### Paso 1: Test en paralelo

```python
import requests

# v1 (legacy)
response_v1 = requests.post("http://localhost:8000/command", json={
    "message": "enciende la luz del salon"
})

# v2 (new)
response_v2 = requests.post("http://localhost:8000/v2/command", json={
    "message": "enciende la luz del salon"
})

# Compare
assert response_v1.json()["result"]["status"] == response_v2.json()["result"]["status"]
```

### Paso 2: Configurar dominio

1. Crear config si no existe: `config/home.json` o `config/care.json`
2. Setear `HALO_DOMAIN` env var
3. Verificar soul: `curl http://localhost:8000/v2/soul`

### Paso 3: Cambiar endpoint

```python
# Antes
response = requests.post("http://localhost:8000/command", ...)

# Después
response = requests.post("http://localhost:8000/v2/command", ...)
```

## Logs y Observabilidad

Los logs se escriben en `data/halo/{domain}/logs/`:

```bash
# Ver telemetría en tiempo real
tail -f data/halo/home/logs/telemetry_$(date +%Y-%m-%d).jsonl | jq .

# Ver clasificaciones
tail -f data/halo/home/logs/classification_$(date +%Y-%m-%d).jsonl | jq .

# Analizar performance
cat data/halo/home/logs/telemetry_*.jsonl | jq '.stage' | sort | uniq -c

# Ver candidatos para learning
ls data/halo/home/learning/candidates/
```

## Troubleshooting

### No se carga el manifest
```bash
# Verificar que existe
cat data/halo/home/soul/manifest.md

# Si no existe, copiar el sample
cp data/halo/home/soul/manifest.md.sample data/halo/home/soul/manifest.md
```

### No se carga la personality
```bash
# Verificar que existe
cat data/halo/home/soul/personality.json

# Si no existe, copiar el sample
cp data/halo/home/soul/personality.json.sample data/halo/home/soul/personality.json
```

### Domain incorrecto
```bash
# Verificar que HALO_DOMAIN está seteado
echo $HALO_DOMAIN

# Si no, setearlo
export HALO_DOMAIN=home  # o care
```

### Telemetría no se escribe
```bash
# Verificar que el directorio existe
ls data/halo/home/logs/

# Verificar permisos
chmod +w data/halo/home/logs/

# Verificar que telemetry está habilitado en config
cat config/home.json | jq .observability.enable_telemetry
```

## Próximos Pasos

1. **Dashboard**: Visualizar métricas y logs
2. **Real-time monitoring**: WebSocket para stream de alertas
3. **Halo X**: Nuevo dominio usando la misma arquitectura
4. **Multi-instance**: Múltiples Halos en paralelo

## Filosofía

> "El rey está libre para moverse."

La v2 API es domain-agnostic. El alma (manifest) define quién es Halo.
El mismo core sirve a Home, Care, y futuros dominios sin cambiar código.
