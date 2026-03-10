# Halo Care - Storage Structure

Este directorio contiene el state y contexto para **Halo Care** (Residencia San Martín, Piso 3).

## Estructura

```
care/
├── soul/                       # Nivel 5: El Alma
│   ├── manifest.md            # Quién es Halo Care
│   ├── personality.json       # Voz, tono, modos de operación
│   └── relationships/         # Conocimiento de operadoras
│       └── carla.json        # Relación con Carla (cuidadora)
│
├── environment/               # Nivel 4: Contexto Ambiental
│   ├── current_state.json    # Estado actual del piso
│   ├── shift_context.json    # Contexto del turno actual
│   └── entities/             # Residentes individuales
│       └── roberto.json      # Perfil y estado de cada residente
│
├── sessions/                  # Nivel 3: Sesiones (turnos)
│   └── shift_*.json          # Turnos de trabajo
│
├── flows/                     # Nivel 2: Flujos de asistencia
│   ├── active/               # Asistencias en progreso
│   └── completed/            # Asistencias completadas
│
├── learning/                  # Sistema de aprendizaje
│   ├── candidates/           # Intervenciones exitosas para review
│   ├── pending_review/       # Pendientes de validación
│   └── golden_examples.json  # Dataset validado de patrones
│
├── context/                   # Contexto del turno
│   ├── conversation.json     # Interacciones actuales
│   └── semantic_memory.json  # Patrones de residentes
│
└── logs/                      # Observabilidad (JSONL)
    ├── telemetry_*.jsonl     # Performance del sistema
    ├── alerts_*.jsonl        # Log de alertas generadas
    └── interventions_*.jsonl # Log de intervenciones
```

## Archivos .sample

Cada directorio tiene archivos `.sample` que documentan el formato esperado:
- **soul/personality.json.sample**: Modos (calm/active/directive), voz, policies
- **soul/relationships/carla.json.sample**: Perfil de operadora
- **environment/current_state.json.sample**: Estado del piso y residentes
- **environment/shift_context.json.sample**: Contexto del turno actual
- **environment/entities/roberto.json.sample**: Perfil de residente
- **sessions/session_example.json.sample**: Sesión de turno
- **flows/active/flow_example.json.sample**: Flujo de asistencia a residente
- **learning/candidates/candidate_example.json.sample**: Intervención exitosa

## Uso

```python
from halo.storage import FileStore

# Crear store para Halo Care
store = FileStore("data/halo/care")

# Leer manifest
manifest = store.read_manifest()

# Leer contexto del turno
shift = store.read("environment", "shift_context")

# Leer perfil de residente
roberto = store.read("environment/entities", "roberto")

# Leer relación con Carla
carla = store.read("soul/relationships", "carla")
```

## Características de Halo Care

- **Operadora**: Carla (cuidadora turno noche)
- **Dominio**: Cuidado geriátrico (vigilancia, alertas, asistencia)
- **Personalidad**: Empática pero competente, voz de colega
- **Horario**: Turno noche 22:00-06:00
- **Filosofía**: Cuidar a quien cuida, automatización progresiva, feedback positivo
- **Crítico**: Sirve a Carla, NO a la institución (privacidad de métricas)

## Diferencias clave con Home

| Aspecto | Home | Care |
|---------|------|------|
| **Usuario** | Homeowner (Ernesto) | Operadora (Carla) |
| **Entidades** | Dispositivos (luces, clima) | Residentes (personas) |
| **Contexto** | Estado de casa | Estado de piso + fatiga operadora |
| **Alertas** | Confirmaciones de comandos | Alertas de residentes (caídas, movimiento) |
| **Flows** | Multi-room automation | Asistencia a residentes |
| **Privacy** | Personal del usuario | Privado para operadora |
| **Modos** | Activo/Silencioso | Calm/Active/Directive |
| **Métricas** | Preferencias aprendidas | Intervenciones exitosas |
