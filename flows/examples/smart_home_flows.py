"""Ejemplos de flows para smart home.

Demuestra cómo usar FlowBuilder para crear flows complejos multi-turno.
Incluye ejemplos task-oriented (simples) y process-oriented (con feedback).
"""

from src.halo.flows import FlowBuilder, SlotType, StepAction


# === FLOW 1: Scene Setup (Stack de 3-4 pasos) ===

scene_setup_flow = (
    FlowBuilder("scene_setup")
    .description("Configurar una escena de iluminación personalizada")

    # Process-oriented: Triggers
    .triggered_by("scene_control", "set_scene")
    .trigger_when_missing("rooms")  # Si falta rooms, iniciar flow
    .can_digress_to("quick_light")  # Permitir interrupción para ajuste rápido

    .add_slot(
        "scene_name",
        SlotType.CHOICE,
        required=True,
        choices=["nocturno", "lectura", "pelicula", "fiesta"],
        prompt_template="¿Qué escena querés configurar? (nocturno, lectura, pelicula, fiesta)",
    )
    .add_slot(
        "rooms",
        SlotType.LIST,
        required=True,
        prompt_template="¿En qué habitaciones aplicar la escena? (separadas por coma)",
    )
    .add_slot(
        "brightness",
        SlotType.NUMBER,
        required=False,
        min_value=0,
        max_value=100,
        default_value=50,
        prompt_template="¿Qué intensidad de luz? (0-100, default 50)",
    )
    .add_step(
        "ask_scene",
        "ask_slot",
        {"slot": "scene_name"},
        description="Pedir nombre de escena",
    )
    .add_step(
        "ask_rooms",
        "ask_slot",
        {"slot": "rooms"},
        description="Pedir habitaciones",
    )
    .add_step(
        "ask_brightness",
        "ask_slot",
        {"slot": "brightness"},
        description="Pedir intensidad (opcional)",
    )
    .add_step(
        "execute",
        "tool_call",
        {"tool": "scene_control"},
        description="Ejecutar configuración de escena",
    )
    .allow_interruptions(True)  # Permitir digresiones
    .auto_fill(True)  # Auto-fill desde contexto
    .tag("lighting", "scenes", "multi-room")
    .build()
)


# === FLOW 2: Climate Schedule (Stack más profundo) ===

climate_schedule_flow = (
    FlowBuilder("climate_schedule")
    .description("Programar horario de climatización")
    .add_slot(
        "room",
        SlotType.TEXT,
        required=True,
        prompt_template="¿En qué habitación configurar el horario?",
    )
    .add_slot(
        "start_time",
        SlotType.TEXT,
        required=True,
        prompt_template="¿A qué hora encender? (formato HH:MM)",
    )
    .add_slot(
        "end_time",
        SlotType.TEXT,
        required=True,
        prompt_template="¿A qué hora apagar? (formato HH:MM)",
    )
    .add_slot(
        "temperature",
        SlotType.NUMBER,
        required=True,
        min_value=16,
        max_value=30,
        prompt_template="¿Qué temperatura objetivo? (16-30°C)",
    )
    .add_slot(
        "days",
        SlotType.LIST,
        required=False,
        default_value=["lun", "mar", "mie", "jue", "vie"],
        prompt_template="¿Qué días? (default: lun-vie)",
    )
    .add_step("collect_room", "ask_slot", {"slot": "room"})
    .add_step("collect_times", "ask_slot", {"slot": "start_time"})
    .add_step("collect_end", "ask_slot", {"slot": "end_time"})
    .add_step("collect_temp", "ask_slot", {"slot": "temperature"})
    .add_step("collect_days", "ask_slot", {"slot": "days"})
    .add_step("execute", "tool_call", {"tool": "schedule_climate"})
    .allow_interruptions(True)
    .tag("climate", "scheduling", "automation")
    .build()
)


# === FLOW 3: Energy Optimization (Conditional branching) ===

def validate_energy_mode(value):
    """Custom validator para energy mode."""
    valid_modes = ["eco", "balanced", "performance"]
    return value.lower() in valid_modes


energy_optimization_flow = (
    FlowBuilder("energy_optimization")
    .description("Optimizar consumo energético de la casa")
    .add_slot(
        "mode",
        SlotType.CHOICE,
        required=True,
        choices=["eco", "balanced", "performance"],
        prompt_template="¿Qué modo de energía? (eco, balanced, performance)",
    )
    .add_slot(
        "auto_adjust",
        SlotType.BOOLEAN,
        required=False,
        default_value=True,
        prompt_template="¿Ajustar automáticamente según ocupación? (si/no)",
    )
    .add_slot(
        "max_temperature",
        SlotType.NUMBER,
        required=False,
        min_value=20,
        max_value=26,
        prompt_template="Temperatura máxima en modo eco? (20-26°C)",
    )
    .add_step("ask_mode", "ask_slot", {"slot": "mode"})
    .add_step("ask_auto", "ask_slot", {"slot": "auto_adjust"})
    .add_step(
        "ask_temp",
        "ask_slot",
        {"slot": "max_temperature"},
        conditions=[
            {"condition": "mode == 'eco'", "next_step": "execute"},
        ],
    )
    .add_step("execute", "tool_call", {"tool": "energy_control"})
    .tag("energy", "optimization", "automation")
    .build()
)


# === FLOW 4: Vacation Mode (Ejemplo de digression) ===

vacation_mode_flow = (
    FlowBuilder("vacation_mode")
    .description("Activar modo vacaciones con configuración completa")
    .add_slot(
        "start_date",
        SlotType.TEXT,
        required=True,
        prompt_template="¿Desde qué fecha? (DD/MM/YYYY)",
    )
    .add_slot(
        "end_date",
        SlotType.TEXT,
        required=True,
        prompt_template="¿Hasta qué fecha? (DD/MM/YYYY)",
    )
    .add_slot(
        "simulate_presence",
        SlotType.BOOLEAN,
        required=True,
        prompt_template="¿Simular presencia con luces aleatorias? (si/no)",
    )
    .add_slot(
        "notifications",
        SlotType.BOOLEAN,
        required=False,
        default_value=True,
        prompt_template="¿Recibir notificaciones de seguridad? (si/no)",
    )
    .add_step("ask_dates", "ask_slot", {"slot": "start_date"})
    .add_step("ask_end", "ask_slot", {"slot": "end_date"})
    .add_step("ask_presence", "ask_slot", {"slot": "simulate_presence"})
    .add_step("ask_notifications", "ask_slot", {"slot": "notifications"})
    .add_step("execute", "tool_call", {"tool": "vacation_mode"})
    .allow_interruptions(True)  # Permitir que interrumpan para ajustar algo
    .tag("vacation", "security", "automation")
    .build()
)


# === FLOW 5: Quick Light Preset (Simple, 2 pasos) ===

quick_light_flow = (
    FlowBuilder("quick_light")
    .description("Ajuste rápido de iluminación")
    .add_slot(
        "room",
        SlotType.TEXT,
        required=True,
        prompt_template="¿Qué habitación?",
    )
    .add_slot(
        "preset",
        SlotType.CHOICE,
        required=True,
        choices=["bright", "dim", "off"],
        prompt_template="¿Qué preset? (bright, dim, off)",
    )
    .add_step("ask_room", "ask_slot", {"slot": "room"})
    .add_step("ask_preset", "ask_slot", {"slot": "preset"})
    .add_step("execute", "tool_call", {"tool": "light_control"})
    .allow_interruptions(False)  # No interrupciones, es muy simple
    .auto_fill(True)  # Auto-fill room desde contexto
    .tag("lighting", "quick", "simple")
    .build()
)


# === FLOW 6: Scene Setup Process-Oriented (con feedback progresivo) ===

scene_setup_process = (
    FlowBuilder("scene_setup_process")
    .description("Configurar escena con feedback progresivo (process-oriented)")

    # Triggers
    .triggered_by("scene_control_advanced")
    .trigger_when_missing("rooms", "scene_name")
    .can_digress_to("quick_light", "climate_control")

    # Slots
    .add_slot(
        "scene_name",
        SlotType.CHOICE,
        required=True,
        choices=["nocturno", "lectura", "película"],
        prompt_template="¿Qué escena? (nocturno, lectura, película)",
    )
    .add_slot(
        "rooms",
        SlotType.LIST,
        required=True,
        prompt_template="¿En qué habitaciones?",
    )
    .add_slot(
        "brightness",
        SlotType.NUMBER,
        required=False,
        min_value=0,
        max_value=100,
        default_value=50,
    )

    # Steps: Task-oriented (compatible con HaloFlowEngine básico)
    .add_step("ask_scene", "ask_slot", {"slot": "scene_name"})
    .add_step("ask_rooms", "ask_slot", {"slot": "rooms"})
    .add_step("execute", "tool_call", {"tool": "scene_control"})

    # NOTE: Para HaloProcessEngine, se podrían usar steps avanzados como:
    # .add_async_step("apply_first", "light_control", {"room": "{rooms[0]}"}, "ask_adjust", "error")
    # .add_step("ask_adjust", StepAction.ASK_USER, {"question": "¿Ajustar brillo?"})
    # .add_condition("check_adjust", "user_wants_adjust", "collect_brightness", "apply_rest")
    # Pero mantenemos compatibilidad con HaloFlowEngine básico por ahora

    .allow_interruptions(True)
    .auto_fill(True)
    .tag("lighting", "process-oriented", "advanced")
    .build()
)


# === Registry de flows ===

SMART_HOME_FLOWS = {
    "scene_setup": scene_setup_flow,
    "climate_schedule": climate_schedule_flow,
    "energy_optimization": energy_optimization_flow,
    "vacation_mode": vacation_mode_flow,
    "quick_light": quick_light_flow,
    "scene_setup_process": scene_setup_process,  # Process-oriented example
}


def register_all_flows(engine):
    """Registrar todos los flows en un engine.

    Args:
        engine: FlowEngine instance

    Example:
        from halo.flows import HaloFlowEngine
        from flows.examples.smart_home_flows import register_all_flows

        engine = HaloFlowEngine()
        register_all_flows(engine)
    """
    for flow_name, flow_def in SMART_HOME_FLOWS.items():
        engine.register_flow(flow_def)
        print(f"✅ Registered flow: {flow_name}")
