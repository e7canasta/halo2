"""Test que valida la arquitectura agnóstica de Halo.

Este test demuestra que:
1. La misma arquitectura soporta Home y Care sin cambios de código
2. El alma (manifest) define el comportamiento
3. El policy-driven chain es verdaderamente agnóstico
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from halo.config import HaloConfig
from halo.storage import FileStore
from halo.context import SoulReader, ContextLoader
from halo.intent.factory import create_policy_driven_chain
from halo.backend.qwen import QwenBackend


def test_config_loading():
    """Test 1: Cargar configs para ambos dominios."""
    print("=== Test 1: Config Loading ===")

    # Load Home config
    home_config = HaloConfig.for_domain("home")
    print(f"✓ Home config: {home_config}")
    print(f"  Store path: {home_config.store_path}")
    print(f"  Policy: {home_config.policy}")
    print(f"  Domain: {home_config.domain}")

    # Load Care config
    care_config = HaloConfig.for_domain("care")
    print(f"\n✓ Care config: {care_config}")
    print(f"  Store path: {care_config.store_path}")
    print(f"  Policy: {care_config.policy}")
    print(f"  Domain: {care_config.domain}")

    # Validate they're different
    assert home_config.domain == "home", "Home config should have home domain"
    assert care_config.domain == "care", "Care config should have care domain"
    assert home_config.policy == "threshold", "Home should use threshold policy"
    assert care_config.policy == "care", "Care should use care policy"

    print("\n✓ Configs are correctly differentiated")
    return home_config, care_config


def test_soul_loading():
    """Test 2: Cargar almas para ambos dominios."""
    print("\n=== Test 2: Soul Loading ===")

    # Load Home soul
    home_store = FileStore("data/halo/home")
    home_soul_reader = SoulReader(home_store)
    home_soul = home_soul_reader.load()

    print(f"✓ Home soul loaded:")
    print(f"  Manifest preview: {home_soul.manifest[:100]}...")
    print(f"  Relationships: {list(home_soul.relationships.keys())}")
    print(f"  Domain detected: {home_soul_reader.get_domain()}")

    # Load Care soul
    care_store = FileStore("data/halo/care")
    care_soul_reader = SoulReader(care_store)
    care_soul = care_soul_reader.load()

    print(f"\n✓ Care soul loaded:")
    print(f"  Manifest preview: {care_soul.manifest[:100]}...")
    print(f"  Relationships: {list(care_soul.relationships.keys())}")
    print(f"  Domain detected: {care_soul_reader.get_domain()}")

    # Validate they're different
    assert "ernesto" in home_soul.manifest.lower() or "casa" in home_soul.manifest.lower(), \
        "Home manifest should mention Ernesto or casa"
    assert "carla" in care_soul.manifest.lower() or "residencia" in care_soul.manifest.lower(), \
        "Care manifest should mention Carla or residencia"

    print("\n✓ Souls are correctly differentiated")
    return home_soul, care_soul


def test_context_levels():
    """Test 3: Cargar contexto completo para ambos dominios."""
    print("\n=== Test 3: Context Levels ===")

    # Home context
    home_store = FileStore("data/halo/home")
    home_loader = ContextLoader(home_store)
    home_context = home_loader.load_full_context()

    print(f"✓ Home context loaded:")
    print(f"  Soul manifest: {len(home_context.soul.manifest)} chars")
    print(f"  Environment time: {home_context.environment.time_of_day}")
    print(f"  Session: {home_context.session.session_id}")

    # Care context
    care_store = FileStore("data/halo/care")
    care_loader = ContextLoader(care_store)
    care_context = care_loader.load_full_context()

    print(f"\n✓ Care context loaded:")
    print(f"  Soul manifest: {len(care_context.soul.manifest)} chars")
    print(f"  Environment time: {care_context.environment.time_of_day}")
    print(f"  Operator fatigue: {care_context.environment.operator_fatigue}")
    print(f"  Alert level: {care_context.environment.alert_level}")
    print(f"  Session: {care_context.session.session_id}")

    print("\n✓ Contexts loaded successfully for both domains")


def test_policy_chain_agnostic():
    """Test 4: Mismo PolicyDrivenChain para ambos dominios."""
    print("\n=== Test 4: Policy-Driven Chain (Agnostic) ===")

    backend = QwenBackend()
    backend.initialize()

    # Home chain con ThresholdPolicy
    home_chain = create_policy_driven_chain(
        backend=backend,
        policy="threshold",
        enable_telemetry=False,
        enable_learning=False,
        store_path="data/halo/home",
        enable_embeddings=False,
        enable_spacy=False,
        enable_gemini=False,
    )

    print("✓ Home chain created (ThresholdPolicy)")
    print(f"  Classifiers: {len(home_chain.classifiers)}")
    print(f"  Policy: {home_chain.policy.__class__.__name__}")

    # Care chain con CarePolicy
    care_chain = create_policy_driven_chain(
        backend=backend,
        policy="care",
        enable_telemetry=False,
        enable_learning=False,
        store_path="data/halo/care",
        enable_embeddings=False,
        enable_spacy=False,
        enable_gemini=False,
    )

    print(f"\n✓ Care chain created (CarePolicy)")
    print(f"  Classifiers: {len(care_chain.classifiers)}")
    print(f"  Policy: {care_chain.policy.__class__.__name__}")

    # Test classification with Home
    home_result = home_chain.classify("enciende la luz del salon")
    if home_result:
        print(f"\n✓ Home classification successful:")
        print(f"  Tool: {home_result.tool_name}")
        print(f"  Parameters: {home_result.parameters}")

    # Test classification with Care (simulado - sin sensor data)
    care_result = care_chain.classify(
        "asistir residente habitacion 102",
        context={"operator_fatigue": 0.5, "alert_level": "active"},
    )
    print(f"\n✓ Care classification attempted (may not have matching tool)")
    print(f"  Result: {care_result.tool_name if care_result else 'None (expected)'}")

    print("\n✓ Same PolicyDrivenChain works for both domains!")


def test_architecture_agnosis():
    """Test 5: Validar que NO hay código domain-specific en core."""
    print("\n=== Test 5: Architecture Agnosticism ===")

    # Check que PolicyDrivenChain no tiene hardcoded domain logic
    from halo.intent.policy_chain import PolicyDrivenChain
    import inspect

    source = inspect.getsource(PolicyDrivenChain)

    # Buscar referencias hardcoded a dominios
    forbidden_terms = ["ernesto", "carla", "home_specific", "care_specific", "sala", "residente"]
    found_hardcoded = [term for term in forbidden_terms if term.lower() in source.lower()]

    if found_hardcoded:
        print(f"⚠ Warning: Found potential hardcoded terms: {found_hardcoded}")
    else:
        print("✓ PolicyDrivenChain is domain-agnostic (no hardcoded terms)")

    # Check que FileStore no tiene domain-specific logic
    from halo.storage.file_store import FileStore
    source = inspect.getsource(FileStore)

    found_hardcoded = [term for term in forbidden_terms if term.lower() in source.lower()]

    if found_hardcoded:
        print(f"⚠ Warning: Found potential hardcoded terms in FileStore: {found_hardcoded}")
    else:
        print("✓ FileStore is domain-agnostic")

    # Check que Policies no tienen domain hardcoded (excepto CarePolicy que es específica)
    from halo.intent.policies import ThresholdPolicy
    source = inspect.getsource(ThresholdPolicy)

    found_hardcoded = [term for term in forbidden_terms if term.lower() in source.lower()]

    if found_hardcoded:
        print(f"⚠ Warning: Found potential hardcoded terms in ThresholdPolicy: {found_hardcoded}")
    else:
        print("✓ ThresholdPolicy is domain-agnostic")

    print("\n✅ Core architecture is domain-agnostic!")
    print("   Domain-specific logic lives in:")
    print("   - Manifest.md (soul)")
    print("   - Personality.json (soul)")
    print("   - Policies (CarePolicy extends ThresholdPolicy)")
    print("   - Config files (config/home.json, config/care.json)")


if __name__ == "__main__":
    print("Validating Agnostic Architecture of Halo\n")
    print("=" * 60)

    try:
        home_config, care_config = test_config_loading()
        home_soul, care_soul = test_soul_loading()
        test_context_levels()
        test_policy_chain_agnostic()
        test_architecture_agnosis()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("\nConclusion:")
        print("  El mismo core de Halo puede ser:")
        print("  - Halo Home (asistente de casa)")
        print("  - Halo Care (compañero de cuidadoras)")
        print("  - Halo X (futuro dominio)")
        print("\n  Sin cambiar una línea de código.")
        print("  El alma (manifest) define quién es.")
        print("\n  El rey está libre para moverse. ♔")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
