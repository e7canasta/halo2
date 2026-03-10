#!/usr/bin/env python3
"""
Comparar Function Calling: FunctionGemma vs Qwen3.5
"""
import os
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

def test_modelo(nombre, modelo_path):
    print(f"\n{'='*60}")
    print(f"🤖 {nombre}")
    print('='*60)

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
                                "description": "Nombre de la ciudad"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "Unidad de temperatura"
                            }
                        },
                        "required": ["city"]
                    }
                }
            }
        ]

        messages = [
            {"role": "system", "content": "Eres un asistente con acceso a herramientas."},
            {"role": "user", "content": "¿Qué temperatura hace en Madrid?"}
        ]

        print("\nPregunta: '¿Qué temperatura hace en Madrid?'")
        print("Tool disponible: get_weather(city, unit)\n")

        # Aplicar template
        try:
            prompt = tokenizer.apply_chat_template(
                messages,
                tools=tools,
                add_generation_prompt=True,
                tokenize=False
            )

            print("✓ Template con tools aplicado")

            # Generar
            inputs = tokenizer(prompt, return_tensors="pt")
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id if tokenizer.eos_token_id else tokenizer.pad_token_id,
            )

            response = tokenizer.decode(outputs[0], skip_special_tokens=False)
            response_only = response[len(prompt):]

            print("\n📝 RESPUESTA:")
            print("-"*60)
            print(response_only[:400])
            print("-"*60)

            # Verificar si llamó a la función
            tiene_call = "get_weather" in response_only or "function" in response_only.lower()
            print(f"\n{'✅' if tiene_call else '❌'} Function call detectado: {'SÍ' if tiene_call else 'NO'}")

            return tiene_call

        except Exception as e:
            print(f"⚠️  Error en template: {e}")
            print("Modelo puede no soportar tools en apply_chat_template")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if os.path.exists('.keys'):
        load_dotenv('.keys')
        hf_token = os.getenv('HF_TOKEN')
        if hf_token:
            from huggingface_hub import login
            login(token=hf_token, add_to_git_credential=False)

    print("\n" + "="*60)
    print("🔧 TEST: Function Calling - FunctionGemma vs Qwen3.5")
    print("="*60)

    modelos = [
        ("FunctionGemma-270M", "google/functiongemma-270m-it"),
        ("Qwen3.5-0.8B", "Qwen/Qwen3.5-0.8B"),
    ]

    resultados = []
    for nombre, path in modelos:
        resultado = test_modelo(nombre, path)
        resultados.append((nombre, resultado))

    # Resumen
    print("\n" + "="*60)
    print("📊 RESUMEN")
    print("="*60)
    for nombre, exito in resultados:
        print(f"{'✅' if exito else '❌'} {nombre:25} {'Soporta function calling' if exito else 'No detectado'}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
