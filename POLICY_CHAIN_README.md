# Policy-Driven Chain Architecture

## Resumen

Hemos implementado una arquitectura de próxima generación para Halo que separa responsabilidades y permite mayor observabilidad y flexibilidad.

## Principios de Diseño

1. **Cada nodo produce, la cadena decide** - Los clasificadores no se invalidan a sí mismos
2. **Observabilidad como interceptor** - No es responsabilidad del nodo, es un ciudadano de primera clase
3. **File-based store** - Transparencia, multi-agente, legibilidad humana
4. **Context awareness multinivel** - El alma, el ambiente, la sesión, el flujo, el comando
5. **Quality > Speed** - Especialmente para hardware y cuidado humano

## Componentes Nuevos

### 1. ClassificationEnvelope
Wrapper que contiene:
- Resultado de la clasificación
- Métricas de confianza (con breakdown)
- Performance (latencia, tokens)
- Diagnósticos
- Contexto enriquecido para siguientes stages

### 2. ChainPolicy
Decide qué hacer con cada resultado:
- **ThresholdPolicy**: Acepta si confidence >= threshold del dominio
- **CarePolicy**: Considera fatiga del operador y nivel de alerta
- **ConsensusPolicy**: Requiere acuerdo de múltiples classifiers

### 3. ChainInterceptor
Observabilidad como side-effect puro:
- **TelemetryInterceptor**: Logs de performance (JSONL)
- **LearningInterceptor**: Captura clasificaciones exitosas para dataset
- **AlertInterceptor**: Detecta situaciones críticas (ej: caídas)
- **ClassificationLogInterceptor**: Log detallado de cada clasificación

### 4. FileStore
Storage inspirado en Claude Code:
```
data/halo/
├── soul/                   # El Alma
│   ├── manifest.md         # Quién es este Halo
│   └── relationships/      # Conoce a los usuarios
├── environment/            # Contexto Ambiental
├── sessions/               # Sesiones
├── flows/                  # Flujos (active/completed)
├── learning/               # Sistema de aprendizaje
├── context/                # Contexto semántico
└── logs/                   # Observabilidad (JSONL)
```

## Uso

### Crear una cadena policy-driven

```python
from halo.backend.qwen import QwenBackend
from halo.intent.factory import create_policy_driven_chain

backend = QwenBackend()
backend.initialize()

# Con ThresholdPolicy (default)
chain = create_policy_driven_chain(
    backend=backend,
    policy="threshold",
    enable_telemetry=True,
    enable_learning=True,
    store_path="data/halo",  # o /var/halo en producción
)

# Clasificar
result = chain.classify("enciende la luz del salon")
```

### Con CarePolicy (para Halo Care)

```python
chain = create_policy_driven_chain(
    backend=backend,
    policy="care",
    enable_telemetry=True,
    store_path="data/halo",
)

# Con contexto de operador fatigado
result = chain.classify(
    "Roberto se levantó",
    context={
        "operator_on_duty": "Carla",
        "operator_fatigue": 0.8,  # 5 horas de turno
        "alert_level": "active",
    },
)
```

### Agregar interceptors custom

```python
from halo.intent import PolicyDrivenChain, ChainInterceptor

class CustomInterceptor(ChainInterceptor):
    def on_stage_complete(self, envelope, context):
        print(f"Stage {envelope.stage_name}: {envelope.confidence:.2f}")

chain = create_policy_driven_chain(backend, policy="threshold")
chain.add_interceptor(CustomInterceptor())
```

## Verificar Logs

```bash
# Ver telemetría en tiempo real
tail -f data/halo/logs/telemetry_$(date +%Y-%m-%d).jsonl | jq .

# Analizar clasificaciones
cat data/halo/logs/classification_*.jsonl | jq '.stage' | sort | uniq -c

# Ver candidatos para learning
ls data/halo/learning/candidates/

# Leer el manifest
cat data/halo/soul/manifest.md
```

## Testing

```bash
# Ejecutar test suite
uv run python test_policy_chain.py
```

Tests incluidos:
1. File Store operations (write/read/move/logs)
2. Basic Classification con telemetría
3. Policy decisions (Threshold vs Care)

## Compatibilidad

La cadena legacy (`ClassifierChain`) sigue funcionando. La nueva `PolicyDrivenChain` coexiste sin romper código existente.

Para migrar gradualmente:
```python
# Legacy (sigue funcionando)
from halo.intent.factory import create_default_chain
chain = create_default_chain(backend)

# New (opt-in)
from halo.intent.factory import create_policy_driven_chain
chain = create_policy_driven_chain(backend)
```

## El Alma de Halo

Cada instancia de Halo tiene un manifest.md que define:
- **Quién es**: Su rol y propósito
- **Personalidad**: Tono, estilo, límites
- **Lo que aprendió**: Conocimiento que evoluciona
- **Filosofía**: Principios que guían sus decisiones

Ver ejemplos:
- `data/halo/soul/manifest.md` - Halo Home
- `data/halo/soul/manifest_care.md` - Halo Care

## Próximos Pasos

Fase 2 (opcional):
- Context Levels (`src/halo/context/levels.py`)
- Soul Reader que carga el manifest al iniciar
- Persistence de flujos complejos
- Metrics dashboard

## Filosofía

> "Halo no es solo un NLU para home automation. Es una plataforma de agencia contextual."

- Halo Home: asistente de hogar
- Halo Care: compañero de cuidadoras
- Halo X: [futuro dominio]

Mismo core, distinta alma. Mismo file store, distintos agentes monitoreando.
