# Halo - Arquitectura Agnóstica

> "El rey está libre para moverse." ♔

## Índice de Documentación

| Documento | Descripción |
|-----------|-------------|
| **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** | Resumen completo de la implementación |
| **[POLICY_CHAIN_README.md](POLICY_CHAIN_README.md)** | Arquitectura policy-driven detallada |
| **[ARCHITECTURE_VALIDATION.md](ARCHITECTURE_VALIDATION.md)** | Validación de agnosticismo |
| **[API_V2_GUIDE.md](API_V2_GUIDE.md)** | Guía de uso de la API v2 |
| **[CLAUDE.md](CLAUDE.md)** | Instrucciones para Claude Code |

## Inicio Rápido

### Halo Home
```bash
export HALO_DOMAIN=home
make server

# Test
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{"message": "enciende la luz del salon"}'
```

### Halo Care
```bash
export HALO_DOMAIN=care
make server

# Test
curl -X POST http://localhost:8000/v2/command \
  -H "Content-Type: application/json" \
  -d '{"message": "Roberto se levantó", "context": {"operator": "carla"}}'
```

## Tests

```bash
# Test agnosticismo
uv run python test_agnostic_architecture.py

# Test policy chain
uv run python test_policy_chain.py

# Test API v2 (requiere server running)
./test_v2_api.sh
```

## Estructura del Proyecto

```
halo/
├── config/
│   ├── home.json               # Config Halo Home
│   └── care.json               # Config Halo Care
│
├── data/halo/
│   ├── home/                   # Storage Halo Home
│   │   ├── soul/               # Manifest, personality, relationships
│   │   ├── environment/        # Current state, entities
│   │   ├── sessions/           # Conversaciones
│   │   ├── flows/              # Flujos multi-paso
│   │   ├── learning/           # Clasificaciones exitosas
│   │   └── logs/               # Telemetría (JSONL)
│   │
│   └── care/                   # Storage Halo Care
│       ├── soul/               # Manifest, personality, relationships
│       ├── environment/        # Current state, shift context, residents
│       ├── sessions/           # Turnos
│       ├── flows/              # Asistencias
│       ├── learning/           # Intervenciones exitosas
│       └── logs/               # Telemetría (JSONL)
│
├── src/halo/
│   ├── config.py               # Config loader
│   ├── storage/
│   │   └── file_store.py       # File-based store
│   ├── context/
│   │   ├── levels.py           # 5 niveles de contexto
│   │   └── soul_reader.py      # Soul loader
│   ├── intent/
│   │   ├── envelope.py         # ClassificationEnvelope
│   │   ├── policies.py         # ThresholdPolicy, CarePolicy
│   │   ├── policy_chain.py     # PolicyDrivenChain
│   │   ├── interceptors.py     # Observabilidad
│   │   └── factory.py          # create_policy_driven_chain()
│   └── api/
│       └── routes/
│           ├── command_routes.py     # v1 (legacy)
│           └── command_routes_v2.py  # v2 (policy-driven)
│
├── test_agnostic_architecture.py    # Test de agnosticismo
├── test_policy_chain.py             # Test de policy chain
└── test_v2_api.sh                   # Test de API v2
```

## Componentes Clave

### 1. Envelope Pattern
```python
@dataclass
class ClassificationEnvelope:
    result: Optional[ClassificationResult]
    stage_name: str
    confidence: float
    latency_ms: float
    diagnostics: dict
    enriched_context: dict
```

### 2. Policies
```python
- ThresholdPolicy: Acepta si confidence >= threshold
- CarePolicy: Considera fatiga del operador
- ConsensusPolicy: Requiere consenso de múltiples classifiers
```

### 3. Interceptors
```python
- TelemetryInterceptor: Logs de performance
- LearningInterceptor: Captura clasificaciones exitosas
- AlertInterceptor: Detecta situaciones críticas
```

### 4. Context Levels (5 Niveles)
```python
HaloContext
├── Soul (Nivel 5): Manifest, personality, relationships
├── Environment (Nivel 4): Current state, operator fatigue
├── Session (Nivel 3): Conversación actual
├── Flow (Nivel 2): Flujo multi-paso
└── Command (Nivel 1): Este input
```

## Filosofía

1. **Cada nodo produce, la cadena decide**
2. **Observabilidad como interceptor**
3. **File-based store** (transparencia, multi-agente)
4. **Context awareness multinivel**
5. **Quality > Speed**

## Diferencias Home vs Care

| Aspecto | Home | Care |
|---------|------|------|
| Usuario | Ernesto | Carla |
| Entidades | Dispositivos | Residentes |
| Contexto | Estado de casa | Fatiga operador |
| Policy | Threshold | Care (fatigue-aware) |
| Modos | Activo/Silencioso | Calm/Active/Directive |

## APIs

### v1 (Legacy)
- `POST /command` - ClassifierChain original
- Compatible con código existente

### v2 (Policy-Driven)
- `POST /v2/command` - PolicyDrivenChain con context levels
- `GET /v2/info` - Info del dominio
- `GET /v2/soul` - Manifest completo
- `GET /v2/context` - Contexto (5 niveles)
- `GET /v2/logs/telemetry` - Telemetría

## Observabilidad

```bash
# Ver telemetría en tiempo real
tail -f data/halo/home/logs/telemetry_$(date +%Y-%m-%d).jsonl | jq .

# Ver clasificaciones
tail -f data/halo/home/logs/classification_$(date +%Y-%m-%d).jsonl | jq .

# Analizar performance
cat data/halo/home/logs/telemetry_*.jsonl | jq '.stage' | sort | uniq -c
```

## El Alma de Halo

Cada instancia tiene un `manifest.md` que define quién es:

**Halo Home**:
```markdown
# Halo Home - Casa de Ernesto

## Quién Soy
Soy el asistente de hogar de Ernesto...

## Mi Personalidad
- Directo, confirmaciones cortas
- Español argentino, informal pero respetuoso
...
```

**Halo Care**:
```markdown
# Care - Residencia San Martín, Piso 3

## Quién Soy
Soy el compañero digital de las cuidadoras del turno noche...

## Mi Personalidad
- Empático pero competente, nunca robótico
- "Te marco ahí, avísame si necesitas algo"
...
```

## Validación

```bash
uv run python test_agnostic_architecture.py
```

**Resultado**:
```
✅ ALL TESTS PASSED!

Conclusion:
  El mismo core de Halo puede ser:
  - Halo Home (asistente de casa)
  - Halo Care (compañero de cuidadoras)
  - Halo X (futuro dominio)

  Sin cambiar una línea de código.
  El alma (manifest) define quién es.

  El rey está libre para moverse. ♔
```

## Próximos Pasos

1. Dashboard de métricas
2. WebSocket para alertas en tiempo real
3. Halo X (tercer dominio)
4. Multi-instance (múltiples Halos en paralelo)

---

**El blues está completo.**
**El rey está libre para moverse.**

🎸 ♔
