"""Test script for policy-driven chain.

Tests the new envelope + policy + interceptor architecture.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from halo.backend.qwen import QwenBackend
from halo.intent.factory import create_policy_driven_chain
from halo.storage import FileStore


def test_basic_classification():
    """Test basic classification with policy-driven chain."""
    print("=== Test 1: Basic Classification ===")

    # Create backend
    backend = QwenBackend()
    backend.initialize()

    # Create chain with temp store
    with tempfile.TemporaryDirectory() as tmpdir:
        chain = create_policy_driven_chain(
            backend=backend,
            policy="threshold",
            enable_telemetry=True,
            enable_learning=True,
            store_path=tmpdir,
            enable_embeddings=False,  # Skip for speed
            enable_spacy=False,  # Skip for speed
            enable_gemini=False,  # Skip (no API key)
        )

        # Test classification
        result = chain.classify("enciende la luz del salon")

        if result:
            print(f"✓ Classification successful!")
            print(f"  Tool: {result.tool_name}")
            print(f"  Parameters: {result.parameters}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Classifier: {result.classifier_used}")
        else:
            print("✗ Classification failed")
            return False

        # Check telemetry logs
        store = FileStore(tmpdir)
        logs = store.read_logs("telemetry")
        print(f"\n✓ Telemetry logs: {len(logs)} entries")
        for log in logs:
            print(f"  - {log['stage']} ({log['latency_ms']:.1f}ms, confidence={log['confidence']:.2f})")

        # Check classification logs
        class_logs = store.read_logs("classification")
        print(f"\n✓ Classification logs: {len(class_logs)} entries")

        # Check learning candidates
        candidates = store.list_keys("learning/candidates")
        print(f"\n✓ Learning candidates: {len(candidates)}")

    return True


def test_policy_decisions():
    """Test different policy decisions."""
    print("\n=== Test 2: Policy Decisions ===")

    backend = QwenBackend()
    backend.initialize()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with threshold policy
        chain_threshold = create_policy_driven_chain(
            backend=backend,
            policy="threshold",
            enable_telemetry=False,
            enable_learning=False,
            store_path=tmpdir,
            enable_embeddings=False,
            enable_spacy=False,
            enable_gemini=False,
        )

        result = chain_threshold.classify("enciende la luz")
        print(f"✓ ThresholdPolicy: {result.tool_name if result else 'None'}")

        # Test with care policy
        chain_care = create_policy_driven_chain(
            backend=backend,
            policy="care",
            enable_telemetry=False,
            enable_learning=False,
            store_path=tmpdir,
            enable_embeddings=False,
            enable_spacy=False,
            enable_gemini=False,
        )

        # Test with operator fatigue context
        result = chain_care.classify(
            "enciende la luz",
            context={"operator_fatigue": 0.8},
        )
        print(f"✓ CarePolicy (fatigued operator): {result.tool_name if result else 'None'}")

    return True


def test_file_store():
    """Test file store operations."""
    print("\n=== Test 3: File Store ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        # Test write/read
        data = {"test": "value", "nested": {"key": "val"}}
        store.write("test_collection", "test_key", data)
        read_data = store.read("test_collection", "test_key")
        assert read_data == data, "Read data doesn't match written data"
        print("✓ Write/Read works")

        # Test list keys
        store.write("test_collection", "key1", {"a": 1})
        store.write("test_collection", "key2", {"b": 2})
        keys = store.list_keys("test_collection")
        assert len(keys) == 3, f"Expected 3 keys, got {len(keys)}"
        print(f"✓ List keys works: {keys}")

        # Test append log
        store.append_log("test_log", {"entry": 1})
        store.append_log("test_log", {"entry": 2})
        logs = store.read_logs("test_log")
        assert len(logs) == 2, f"Expected 2 log entries, got {len(logs)}"
        print(f"✓ Append log works: {len(logs)} entries")

        # Test move
        moved = store.move("test_collection", "archived", "key1")
        assert moved, "Move failed"
        assert "key1" not in store.list_keys("test_collection"), "Key still in source"
        assert "key1" in store.list_keys("archived"), "Key not in destination"
        print("✓ Move works")

        # Test manifest
        manifest = "# Test Manifest\n\nThis is a test."
        store.write_manifest(manifest)
        read_manifest = store.read_manifest()
        assert read_manifest == manifest, "Manifest doesn't match"
        print("✓ Manifest works")

    return True


if __name__ == "__main__":
    print("Testing Policy-Driven Chain Architecture\n")

    try:
        success = True
        success &= test_file_store()
        success &= test_basic_classification()
        success &= test_policy_decisions()

        if success:
            print("\n✅ All tests passed!")
        else:
            print("\n❌ Some tests failed")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
