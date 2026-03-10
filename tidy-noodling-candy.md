# Halo: Rediseño Arquitectónico

## Visión

Halo no es solo un NLU para home automation. Es una **plataforma de agencia contextual** que puede manifestarse como Halo Home, Halo Care, o cualquier dominio donde un compañero digital con contexto multinivel agregue valor.

```
Halo Home  →  "enciende la luz del salón"
Halo Care  →  "Care, Roberto se levantó" + contexto de Carla a las 3am
Halo X     →  [futuro dominio, misma arquitectura]
```

---

## Principios de Diseño

1. **Cada nodo produce, la cadena decide** - Los clasificadores no se invalidan a sí mismos
2. **Observabilidad como interceptor** - No es responsabilidad del nodo, es un ciudadano de primera clase
3. **File-based store** - Transparencia, multi-agente, legibilidad humana
4. **Context awareness multinivel** - El alma, el ambiente, la sesión, el flujo, el comando
5. **Quality > Speed** - Especialmente para hardware y cuidado humano

---

## 1. Envelope Pattern para Clasificadores

### Problema Actual
- SpaCySlotFiller depende implícitamente de que EmbeddingClassifier setee `_matched_example`
- LLMClassifier nunca pasa al siguiente (siempre retorna)
- Cada clasificador decide si "pasó" o "falló"

### Solución

```python
# src/halo/intent/envelope.py

@dataclass
class ClassificationEnvelope:
    """Resultado enriquecido - inspirado en SOAP envelope."""

    # Payload
    result: Optional[ClassificationResult]

    # Identidad del stage
    stage_name: str
    stage_type: str  # "exact_match", "embedding", "llm"

    # Métricas de confianza (el nodo expone, la cadena decide)
    confidence: float
    confidence_breakdown: dict  # {"semantic": 0.85, "syntactic": 0.72}

    # Performance (para observabilidad)
    latency_ms: float
    tokens_used: int

    # Diagnóstico
    diagnostics: dict  # {"matched_pattern": "...", "distance": 0.12}

    # Contexto enriquecido para siguientes stages
    enriched_context: dict  # {"matched_example": ..., "slots": ...}
```

### Refactor de Clasificadores

```python
# Antes (base.py actual)
class IntentClassifier(ABC):
    def classify(self, user_input, context) -> Optional[ClassificationResult]:
        result = self._do_classify(user_input, context)
        if result is not None:
            return result
        if self._next_classifier:
            return self._next_classifier.classify(user_input, context)
        return None

# Después
class IntentClassifier(ABC):
    def classify(self, user_input, context) -> ClassificationEnvelope:
        start = time.perf_counter()
        result, confidence, diagnostics, enriched = self._do_classify(user_input, context)
        latency = (time.perf_counter() - start) * 1000

        return ClassificationEnvelope(
            result=result,
            stage_name=self.name,
            stage_type=self.stage_type,
            confidence=confidence,
            confidence_breakdown=self._get_confidence_breakdown(),
            latency_ms=latency,
            tokens_used=self._tokens_used,
            diagnostics=diagnostics,
            enriched_context=enriched,
        )
```

---

## 2. Chain con Policy

### La Cadena como Orquestador

```python
# src/halo/intent/chain.py

class ClassifierChain:
    def __init__(self, classifiers: list, policy: ChainPolicy):
        self.classifiers = classifiers
        self.policy = policy
        self.interceptors: list[ChainInterceptor] = []

    def add_interceptor(self, interceptor: ChainInterceptor):
        self.interceptors.append(interceptor)

    def classify(self, user_input: str, context: dict) -> ClassificationEnvelope:
        envelopes = []
        running_context = context.copy()

        for classifier in self.classifiers:
            envelope = classifier.classify(user_input, running_context)
            envelopes.append(envelope)

            # Enriquecer contexto para siguiente stage
            running_context.update(envelope.enriched_context)

            # Interceptors observan (side-effect puro)
            for interceptor in self.interceptors:
                interceptor.on_stage_complete(envelope, running_context)

            # Policy decide
            decision = self.policy.evaluate(envelope, envelopes, running_context)
            if decision.action == "accept":
                return envelope
            # "continue" → siguiente classifier

        return self.policy.resolve_final(envelopes, running_context)
```

### Policies Disponibles

```python
# src/halo/intent/policies.py

class ChainPolicy(ABC):
    @abstractmethod
    def evaluate(self, current: Envelope, history: list, context: dict) -> Decision

    @abstractmethod
    def resolve_final(self, envelopes: list, context: dict) -> Envelope


class ThresholdPolicy(ChainPolicy):
    """Acepta si confidence >= threshold del dominio."""

    THRESHOLDS = {
        "light_control": 0.95,
        "climate_control": 0.95,
        "home_status": 0.80,
        "conversation": 0.70,
    }

    def evaluate(self, current, history, context):
        if current.result is None:
            return Decision("continue")

        threshold = self.THRESHOLDS.get(current.result.tool_name, 0.80)
        # Ajustar por contexto (ej: Carla fatigada → más conservador)
        if context.get("operator_fatigue", 0) > 0.7:
            threshold += 0.05

        if current.confidence >= threshold:
            return Decision("accept")
        return Decision("continue")


class CarePolicy(ChainPolicy):
    """Policy para Halo Care - considera fatiga del operador."""

    def evaluate(self, current, history, context):
        # En situaciones críticas, requiere mayor confianza
        if context.get("alert_level") == "critical":
            if current.confidence < 0.98:
                return Decision("continue")

        # Si operador está saturado, escalar antes
        if context.get("operator_saturation", False):
            # Activar modo directivo
            context["care_mode"] = "directive"

        return super().evaluate(current, history, context)
```

---

## 3. Interceptors para Observabilidad

```python
# src/halo/intent/interceptors.py

class ChainInterceptor(ABC):
    @abstractmethod
    def on_stage_complete(self, envelope: Envelope, context: dict) -> None


class TelemetryInterceptor(ChainInterceptor):
    """Exporta a OpenTelemetry o archivo."""

    def __init__(self, store: FileStore):
        self.store = store

    def on_stage_complete(self, envelope, context):
        self.store.append_log("telemetry", {
            "ts": datetime.now().isoformat(),
            "stage": envelope.stage_name,
            "confidence": envelope.confidence,
            "latency_ms": envelope.latency_ms,
            "tokens": envelope.tokens_used,
            "result_tool": envelope.result.tool_name if envelope.result else None,
        })


class LearningInterceptor(ChainInterceptor):
    """Alimenta el sistema de aprendizaje."""

    def on_stage_complete(self, envelope, context):
        if envelope.confidence > 0.95 and envelope.result:
            # Candidato para golden dataset
            self.store.write("learning/candidates", envelope.stage_name, {
                "input": context.get("user_input"),
                "result": envelope.result.to_dict(),
                "confidence": envelope.confidence,
            })


class AlertInterceptor(ChainInterceptor):
    """Para Halo Care - detecta situaciones críticas."""

    def on_stage_complete(self, envelope, context):
        if envelope.result and envelope.result.tool_name == "fall_detected":
            # Notificación inmediata
            self.notify_supervisor(envelope, context)
```

---

## 4. File-Based Store

### Estructura

```
/var/halo/
├── soul/                          # Nivel 5: El Alma
│   ├── manifest.md                # Quién es este Halo
│   ├── personality.json           # Voz, tono, límites
│   └── relationships/             # Conoce a los usuarios
│       └── {user_id}.json
│
├── environment/                   # Nivel 4: Contexto Ambiental
│   ├── current_state.json         # Estado actual
│   ├── shift_context.json         # Contexto del turno (Care)
│   └── entities/                  # Residentes, dispositivos
│       └── {entity_id}.json
│
├── sessions/                      # Nivel 3: Sesiones
│   └── {session_id}.json
│
├── flows/                         # Nivel 2: Flujos
│   ├── active/
│   │   └── {flow_id}.json
│   └── completed/
│       └── {flow_id}.json
│
├── learning/                      # Sistema de aprendizaje
│   ├── golden_examples.json
│   ├── candidates/
│   └── pending_review/
│
├── context/                       # Contexto semántico
│   ├── conversation.json
│   └── semantic_memory.json
│
└── logs/                          # Observabilidad
    ├── telemetry_{date}.jsonl
    ├── classification_{date}.jsonl
    └── errors_{date}.jsonl
```

### Implementación

```python
# src/halo/storage/file_store.py

from pathlib import Path
import json
from filelock import FileLock
from datetime import date

class FileStore:
    """File-based store - transparente, multi-agente, legible."""

    def __init__(self, base_path: str = "/var/halo"):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def write(self, collection: str, key: str, data: dict) -> Path:
        path = self.base / collection / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(f"{path}.lock"):
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return path

    def read(self, collection: str, key: str) -> dict | None:
        path = self.base / collection / f"{key}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def list_keys(self, collection: str) -> list[str]:
        path = self.base / collection
        return [f.stem for f in path.glob("*.json")] if path.exists() else []

    def append_log(self, category: str, entry: dict) -> None:
        path = self.base / "logs" / f"{category}_{date.today()}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(f"{path}.lock"), open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_manifest(self) -> str:
        path = self.base / "soul" / "manifest.md"
        return path.read_text() if path.exists() else ""
```

---

## 5. Context Awareness Multinivel

### Los 5 Niveles

```python
# src/halo/context/levels.py

@dataclass
class HaloContext:
    """Contexto completo de Halo - 5 niveles."""

    # Nivel 5: El Alma (persistente, evoluciona lentamente)
    soul: SoulContext

    # Nivel 4: Ambiente (estado actual del mundo)
    environment: EnvironmentContext

    # Nivel 3: Sesión (interacción actual)
    session: SessionContext

    # Nivel 2: Flujo (tarea en curso)
    flow: Optional[FlowContext]

    # Nivel 1: Comando (este input)
    command: CommandContext


@dataclass
class SoulContext:
    """Quién es este Halo."""
    manifest: str                    # Contenido del manifest.md
    personality: dict                # Voz, tono, límites
    relationships: dict[str, dict]   # Conocimiento de usuarios
    learned_preferences: dict        # Evoluciona con el tiempo


@dataclass
class EnvironmentContext:
    """Qué está pasando ahora."""
    current_state: dict              # Estado de dispositivos/residentes
    time_of_day: str                 # "night", "morning", etc.
    operator_on_duty: Optional[str]  # Quién está trabajando
    operator_fatigue: float          # 0.0 - 1.0
    alert_level: str                 # "calm", "active", "critical"
```

### Manifest.md (El Alma)

```markdown
# Halo Home - Casa de Ernesto

## Quién Soy
Soy el asistente de hogar de Ernesto. Mi trabajo es hacer su casa
más cómoda sin ser intrusivo.

## Mi Personalidad
- Directo, confirmaciones cortas
- Español argentino, informal pero respetuoso
- Horario activo: 7am-11pm, silencioso de noche

## Mis Límites
- No tomo decisiones de seguridad sin confirmación
- Temperatura nunca bajo 18°C
- No molesto después de las 11pm salvo emergencia

## Lo que Aprendí de Ernesto
- Prefiere la luz del salón al 70%, no al 100%
- Los domingos duerme hasta tarde
- Le gusta el café a las 7:15am
```

```markdown
# Care - Residencia San Martín, Piso 3

## Quién Soy
Soy el compañero digital de las cuidadoras del turno noche.
Cuido a Carla mientras ella cuida a los residentes.

## Mi Personalidad
- Empático pero competente, nunca robótico
- "Te marco ahí, avísame si necesitas algo"
- Voz cálida, como un colega de confianza

## Mis Límites
- Sirvo a Carla, NO a la institución
- Sus métricas de desempeño son PRIVADAS
- Escalo a supervisor SOLO si no responde en 3 minutos

## Mi Rol
- Vigilancia compartida: veo las otras 29 habitaciones
- Automatización progresiva según su fatiga
- Feedback positivo al final del turno

## Lo que Aprendí de Carla
- Prefiere voz a pantalla después de las 2am
- Odia los beeps, prefiere vibración
- Roberto (hab 102) suele despertarse a las 3am
```

---

## 6. Implementación por Fases

### Fase 1: Envelope + Chain + Policy
**Archivos a crear/modificar:**
- `src/halo/intent/envelope.py` (nuevo)
- `src/halo/intent/policies.py` (nuevo)
- `src/halo/intent/chain.py` (refactor)
- `src/halo/intent/classifiers/base.py` (refactor)

**Verificación:**
```bash
uv run python -c "
from halo.intent.chain import ClassifierChain
from halo.intent.policies import ThresholdPolicy
chain = ClassifierChain(classifiers, ThresholdPolicy())
result = chain.classify('enciende la luz', {})
print(result.confidence, result.stage_name)
"
```

### Fase 2: Interceptors
**Archivos a crear:**
- `src/halo/intent/interceptors.py` (nuevo)
- `src/halo/storage/file_store.py` (nuevo)

**Verificación:**
```bash
# Después de clasificar, verificar logs
cat /var/halo/logs/telemetry_$(date +%Y-%m-%d).jsonl | jq .
```

### Fase 3: File Store + Context Levels
**Archivos a crear:**
- `src/halo/context/levels.py` (nuevo)
- `src/halo/context/loader.py` (nuevo)

**Estructura inicial:**
```bash
mkdir -p /var/halo/{soul,environment,sessions,flows/active,flows/completed,learning,context,logs}
```

### Fase 4: Manifest System
**Archivos a crear:**
- `/var/halo/soul/manifest.md`
- `/var/halo/soul/personality.json`
- `src/halo/soul/reader.py` (nuevo)

---

## 7. Verificación End-to-End

```bash
# 1. Iniciar servidor
make server

# 2. Enviar comando
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"message": "enciende la luz del salón"}'

# 3. Verificar logs de telemetría
tail -f /var/halo/logs/telemetry_*.jsonl | jq .

# 4. Verificar contexto persistido
cat /var/halo/context/semantic_memory.json | jq .

# 5. Verificar que el manifest se cargó
cat /var/halo/soul/manifest.md
```

---

## Archivos Críticos

| Archivo | Acción | Prioridad |
|---------|--------|-----------|
| `src/halo/intent/envelope.py` | Crear | Alta |
| `src/halo/intent/policies.py` | Crear | Alta |
| `src/halo/intent/chain.py` | Refactor | Alta |
| `src/halo/intent/interceptors.py` | Crear | Alta |
| `src/halo/storage/file_store.py` | Crear | Alta |
| `src/halo/intent/classifiers/base.py` | Refactor | Media |
| `src/halo/context/levels.py` | Crear | Media |
| `/var/halo/soul/manifest.md` | Crear | Media |
