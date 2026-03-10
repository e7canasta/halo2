# Halo Home - Storage Structure

Este directorio contiene el state y contexto para **Halo Home** (casa de Ernesto).

## Estructura

```
home/
├── soul/                       # Nivel 5: El Alma
│   ├── manifest.md            # Quién es Halo Home
│   ├── personality.json       # Voz, tono, límites, preferencias
│   └── relationships/         # Conocimiento de usuarios
│       └── ernesto.json       # Relación con Ernesto
│
├── environment/               # Nivel 4: Contexto Ambiental
│   ├── current_state.json    # Estado actual de la casa
│   └── entities/             # Dispositivos individuales
│       └── sala_luz.json     # Estado y configuración de cada dispositivo
│
├── sessions/                  # Nivel 3: Sesiones de interacción
│   └── session_*.json        # Conversaciones activas
│
├── flows/                     # Nivel 2: Flujos multi-paso
│   ├── active/               # Flujos en progreso
│   └── completed/            # Flujos completados (histórico)
│
├── learning/                  # Sistema de aprendizaje
│   ├── candidates/           # Clasificaciones exitosas para review
│   ├── pending_review/       # Pendientes de validación
│   └── golden_examples.json  # Dataset validado
│
├── context/                   # Contexto conversacional
│   ├── conversation.json     # Historial reciente
│   └── semantic_memory.json  # Memoria de largo plazo
│
└── logs/                      # Observabilidad (JSONL)
    ├── telemetry_*.jsonl     # Performance de classifiers
    ├── classification_*.jsonl # Clasificaciones detalladas
    └── errors_*.jsonl        # Errores y excepciones
```

## Archivos .sample

Cada directorio tiene archivos `.sample` que documentan el formato esperado:
- **soul/personality.json.sample**: Configuración de personalidad
- **soul/relationships/ernesto.json.sample**: Perfil de usuario
- **environment/current_state.json.sample**: Estado actual de la casa
- **environment/entities/sala_luz.json.sample**: Configuración de dispositivo
- **sessions/session_example.json.sample**: Sesión de interacción
- **flows/active/flow_example.json.sample**: Flujo multi-paso
- **learning/candidates/candidate_example.json.sample**: Candidato para learning

## Uso

```python
from halo.storage import FileStore

# Crear store para Halo Home
store = FileStore("data/halo/home")

# Leer manifest
manifest = store.read_manifest()

# Leer estado actual
state = store.read("environment", "current_state")

# Leer relación con Ernesto
ernesto = store.read("soul/relationships", "ernesto")
```

## Características de Halo Home

- **Usuario**: Ernesto (homeowner)
- **Dominio**: Home automation (luces, clima, persianas)
- **Personalidad**: Directo, español argentino, no intrusivo
- **Horario**: Activo 07:00-23:00, silencioso de noche
- **Filosofía**: Quality > Speed, context awareness, aprendizaje continuo
