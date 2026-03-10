#!/usr/bin/env python3
"""
Test Function Calling: FunctionGemma
"""

import os
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import re


def test_function_gemma(modelo_path):
    print(f"\n{'=' * 60}")
    print(f"🤖 FunctionGemma")
    print("=" * 60)

    try:
        tokenizer = AutoTokenizer.from_pretrained(modelo_path)
        model = AutoModelForCausalLM.from_pretrained(
            modelo_path,
            torch_dtype=torch.float32,
            device_map="cpu",
            low_cpu_mem_usage=True,
        )

        # Definir herramientas
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Obtiene el clima actual de una ciudad",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "Nombre de la ciudad",
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "Unidad de temperatura",
                            },
                        },
                        "required": ["city"],
                    },
                },
            }
        ]

        messages = [
            {
                "role": "developer",
                "content": "You are a model that can do function calling with the following functions",
            },
            {"role": "user", "content": "¿Qué temperatura hace en Madrid?"},
        ]

        print("\nPregunta: '¿Qué temperatura hace en Madrid?'")
        print("Tool disponible: get_weather(city, unit)\n")

        # Aplicar template con tools
        try:
            prompt = tokenizer.apply_chat_template(
                messages, tools=tools, add_generation_prompt=True, tokenize=False
            )

            print("✓ Template con tools aplicado")

            # Generar function call
            inputs = tokenizer(prompt, return_tensors="pt")
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
                if tokenizer.eos_token_id
                else tokenizer.pad_token_id,
            )

            response = tokenizer.decode(outputs[0], skip_special_tokens=False)
            generated = response[len(prompt) :]

            print("\n📝 FUNCTION CALL:")
            print("-" * 60)
            print(generated[:400])
            print("-" * 60)

            # Parse function call
            call_match = re.search(
                r"<start_function_call>call:(\w+)\{(.+?)\}<end_function_call>",
                generated,
            )
            if call_match:
                func_name, args_str = call_match.groups()
                print(f"✅ Function call detectado: {func_name}")

                # Simular ejecución (en producción, llama a la función real)
                if func_name == "get_weather":
                    result = {
                        "temperature": 25,
                        "unit": "celsius",
                        "weather": "soleado",
                    }
                    # Append response to messages
                    messages.append(
                        {
                            "role": "tool",
                            "content": {"name": func_name, "response": result},
                        }
                    )

                    # Generate final response
                    final_prompt = tokenizer.apply_chat_template(
                        messages,
                        tools=tools,
                        add_generation_prompt=True,
                        tokenize=False,
                    )
                    final_inputs = tokenizer(final_prompt, return_tensors="pt")
                    final_outputs = model.generate(
                        **final_inputs,
                        max_new_tokens=50,
                        do_sample=False,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                    final_response = tokenizer.decode(
                        final_outputs[0], skip_special_tokens=True
                    )[len(final_prompt) :]

                    print("\n📝 FINAL RESPONSE:")
                    print("-" * 60)
                    print(final_response[:400])
                    print("-" * 60)

                    return True
            else:
                print("❌ No se detectó function call válido")
                return False

        except Exception as e:
            print(f"⚠️  Error en template: {e}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    if os.path.exists(".keys"):
        load_dotenv(".keys")
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            from huggingface_hub import login

            login(token=hf_token, add_to_git_credential=False)

    modelo_path = "google/functiongemma-270m-it"
    test_function_gemma(modelo_path)


if __name__ == "__main__":
    main()
