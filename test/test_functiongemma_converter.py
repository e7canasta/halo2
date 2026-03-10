#!/usr/bin/env python3
"""
Test FunctionGemma converter.

Tests:
1. Tool to declaration conversion
2. Params to function call conversion
3. Function call parsing
"""

from halo.nlp.functiongemma.converter import HaloToFunctionGemmaConverter
from halo.tools.registry import Tool


def test_tool_to_declaration():
    """Test converting Halo Tool to FunctionGemma declaration."""
    print("=" * 70)
    print("TEST 1: Tool → Declaration")
    print("=" * 70)

    tool = Tool(
        name="light_control",
        description="Control de luces: encender, apagar, atenuar",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "dim", "brightness"],
                    "description": "Acción a realizar",
                },
                "room": {
                    "type": "string",
                    "description": "Habitación donde está la luz",
                },
                "level": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["action", "room"],
        },
        handler=lambda **kwargs: None,
    )

    converter = HaloToFunctionGemmaConverter()
    declaration = converter.tool_to_declaration(tool)

    print(f"\nInput Tool:")
    print(f"  Name: {tool.name}")
    print(f"  Description: {tool.description}")
    print(f"\nOutput Declaration:")
    print(f"  {declaration}")

    # Verify format
    assert declaration.startswith("<start_function_declaration>")
    assert declaration.endswith("<end_function_declaration>")
    assert "light_control" in declaration
    assert "<escape>Control de luces" in declaration
    print("\n✅ PASSED: Tool to declaration conversion")


def test_params_to_call():
    """Test converting parameters to function call."""
    print("\n" + "=" * 70)
    print("TEST 2: Params → Function Call")
    print("=" * 70)

    converter = HaloToFunctionGemmaConverter()

    # Test case 1: String params
    tool_name = "light_control"
    params = {"action": "on", "room": "salon"}
    call = converter.params_to_call(tool_name, params)

    print(f"\nInput:")
    print(f"  Tool: {tool_name}")
    print(f"  Params: {params}")
    print(f"\nOutput:")
    print(f"  {call}")

    assert call.startswith("<start_function_call>")
    assert call.endswith("<end_function_call>")
    assert "call:light_control" in call
    assert "<escape>on<escape>" in call
    assert "<escape>salon<escape>" in call
    print("\n✅ PASSED: Params to function call (strings)")

    # Test case 2: Mixed types
    params2 = {"action": "brightness", "room": "cocina", "level": 75}
    call2 = converter.params_to_call(tool_name, params2)

    print(f"\nTest case 2:")
    print(f"  Params: {params2}")
    print(f"  Output: {call2}")

    assert "<escape>brightness<escape>" in call2
    assert "level:75" in call2
    print("✅ PASSED: Params to function call (mixed types)")


def test_parse_function_call():
    """Test parsing FunctionGemma output."""
    print("\n" + "=" * 70)
    print("TEST 3: Parse Function Call")
    print("=" * 70)

    converter = HaloToFunctionGemmaConverter()

    # Test case 1: Simple call
    output1 = "<start_function_call>call:light_control{action:<escape>on<escape>,room:<escape>salon<escape>}<end_function_call>"
    tool_name, params = converter.parse_function_call(output1)

    print(f"\nInput:")
    print(f"  {output1}")
    print(f"\nParsed:")
    print(f"  Tool: {tool_name}")
    print(f"  Params: {params}")

    assert tool_name == "light_control"
    assert params == {"action": "on", "room": "salon"}
    print("\n✅ PASSED: Parse simple function call")

    # Test case 2: With numbers
    output2 = "<start_function_call>call:climate_control{action:<escape>set_temp<escape>,room:<escape>sala<escape>,temperature:22}<end_function_call>"
    tool_name2, params2 = converter.parse_function_call(output2)

    print(f"\nTest case 2:")
    print(f"  Input: {output2}")
    print(f"  Tool: {tool_name2}")
    print(f"  Params: {params2}")

    assert tool_name2 == "climate_control"
    assert params2["temperature"] == 22
    print("✅ PASSED: Parse function call with numbers")

    # Test case 3: No function call
    output3 = "No puedo ayudarte con eso."
    tool_name3, params3 = converter.parse_function_call(output3)

    assert tool_name3 is None
    assert params3 == {}
    print("\n✅ PASSED: Parse non-function-call output")


def main():
    """Run all tests."""
    print("\n🧪 Testing FunctionGemma Converter")

    try:
        test_tool_to_declaration()
        test_params_to_call()
        test_parse_function_call()

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED")
        print("=" * 70)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
