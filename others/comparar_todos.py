#!/usr/bin/env python3
"""
📊 Comparador COMPLETO - Todos los 9 modelos
Uso: python comparar_todos.py "pregunta" [max_tokens]
"""
import os
import sys
import time
import psutil
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# TODOS los 8 modelos (≤0.8B)
MODELOS = [
    {
        "key": "smollm-135",
        "name": "HuggingFaceTB/SmolLM2-135M",
        "params": "135M",
        "type": "base"
    },
    {
        "key": "smollm-135-it",
        "name": "HuggingFaceTB/SmolLM2-135M-Instruct",
        "params": "135M",
        "type": "instruct"
    },
    {
        "key": "gemma3-270",
        "name": "google/gemma-3-270m",
        "params": "270M",
        "type": "base"
    },
    {
        "key": "gemma3-270-it",
        "name": "google/gemma-3-270m-it",
        "params": "270M",
        "type": "instruct"
    },
    {
        "key": "functiongemma-270",
        "name": "google/functiongemma-270m-it",
        "params": "270M",
        "type": "function"
    },
    {
        "key": "smollm-360",
        "name": "HuggingFaceTB/SmolLM2-360M",
        "params": "360M",
        "type": "base"
    },
    {
        "key": "smollm-360-it",
        "name": "HuggingFaceTB/SmolLM2-360M-Instruct",
        "params": "360M",
        "type": "instruct"
    },
    {
        "key": "qwen25",
        "name": "Qwen/Qwen2.5-0.5B-Instruct",
        "params": "500M",
        "type": "instruct"
    },
    {
        "key": "qwen35",
        "name": "Qwen/Qwen3.5-0.8B",
        "params": "800M",
        "type": "base"
    }
]

def get_memory_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def probar_modelo(modelo_info, pregunta, max_tokens):
    """Prueba un modelo y retorna resultados"""
    nombre_corto = modelo_info['name'].split('/')[-1]
    print(f"\n{'='*60}")
    print(f"Probando: {nombre_corto} ({modelo_info['params']}) [{modelo_info['type']}]")
    print('='*60)

    try:
        mem_antes = get_memory_mb()
        start_load = time.time()

        tokenizer = AutoTokenizer.from_pretrained(modelo_info['name'])
        model = AutoModelForCausalLM.from_pretrained(
            modelo_info['name'],
            torch_dtype=torch.float32,
            device_map="cpu",
            low_cpu_mem_usage=True,
        )

        tiempo_carga = time.time() - start_load
        ram_modelo = get_memory_mb() - mem_antes

        print(f"✓ Cargado en {tiempo_carga:.1f}s, RAM: {ram_modelo:.0f}MB")

        # Generar
        start_gen = time.time()
        inputs = tokenizer(pregunta, return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id if tokenizer.eos_token_id else tokenizer.pad_token_id,
        )

        tiempo_gen = time.time() - start_gen
        respuesta = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Limpiar respuesta
        if respuesta.startswith(pregunta):
            respuesta = respuesta[len(pregunta):].strip()

        tokens_seg = max_tokens / tiempo_gen if tiempo_gen > 0 else 0

        print(f"✓ Generado en {tiempo_gen:.2f}s ({tokens_seg:.1f} tok/s)")
        print(f"\nRespuesta: {respuesta[:100]}...")

        # Limpiar memoria
        del model
        del tokenizer
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

        return {
            "nombre": nombre_corto,
            "params": modelo_info['params'],
            "type": modelo_info['type'],
            "ram_mb": int(ram_modelo),
            "tiempo_carga": tiempo_carga,
            "tiempo_gen": tiempo_gen,
            "tokens_seg": tokens_seg,
            "respuesta": respuesta[:60]
        }

    except Exception as e:
        error_msg = str(e)
        if "couldn't connect" in error_msg or "gated" in error_msg.lower():
            print(f"⚠️  Modelo requiere acceso en HuggingFace")
        else:
            print(f"❌ Error: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("\n📊 Comparador COMPLETO - 9 Modelos Edge")
        print("="*60)
        print("\nUso: uv run python comparar_todos.py \"pregunta\" [max_tokens]")
        print("\nEjemplo:")
        print('  uv run python comparar_todos.py "¿Qué es Python?" 20')
        print("\nProbará estos 9 modelos (≤0.8B):")
        for m in MODELOS:
            print(f"  • {m['name']:45} {m['params']:>6} [{m['type']}]")
        sys.exit(0)

    pregunta = sys.argv[1]
    max_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    # Autenticar
    if os.path.exists('.keys'):
        load_dotenv('.keys')
        hf_token = os.getenv('HF_TOKEN')
        if hf_token:
            from huggingface_hub import login
            login(token=hf_token, add_to_git_credential=False)

    print("\n" + "="*60)
    print("📊 COMPARACIÓN COMPLETA - 9 MODELOS EDGE")
    print("="*60)
    print(f"\nPregunta: {pregunta}")
    print(f"Tokens a generar: {max_tokens}\n")

    resultados = []
    for modelo in MODELOS:
        resultado = probar_modelo(modelo, pregunta, max_tokens)
        if resultado:
            resultados.append(resultado)
        time.sleep(0.5)  # Pausa entre modelos

    # Tabla comparativa
    if resultados:
        print("\n" + "="*60)
        print("📊 TABLA COMPARATIVA")
        print("="*60)
        print(f"{'Modelo':<30} {'Params':<8} {'Type':<8} {'RAM':<8} {'Tok/s':<8}")
        print("-"*60)

        for r in resultados:
            print(f"{r['nombre']:<30} {r['params']:<8} {r['type']:<8} {r['ram_mb']:>5}MB  {r['tokens_seg']:>6.1f}")

        print("="*60)

        # Rankings
        print("\n🏆 RANKINGS:")
        print("-"*60)

        mas_rapido = max(resultados, key=lambda x: x['tokens_seg'])
        print(f"⚡ Más rápido: {mas_rapido['nombre']} ({mas_rapido['tokens_seg']:.1f} tok/s)")

        menos_ram = min(resultados, key=lambda x: x['ram_mb'])
        print(f"💾 Menos RAM: {menos_ram['nombre']} ({menos_ram['ram_mb']}MB)")

        # Comparar base vs instruct
        print("\n📊 BASE vs INSTRUCT:")
        print("-"*60)

        base_models = [r for r in resultados if r['type'] == 'base']
        instruct_models = [r for r in resultados if r['type'] == 'instruct']

        if base_models and instruct_models:
            avg_base = sum(r['tokens_seg'] for r in base_models) / len(base_models)
            avg_instruct = sum(r['tokens_seg'] for r in instruct_models) / len(instruct_models)

            print(f"Promedio BASE: {avg_base:.1f} tok/s")
            print(f"Promedio INSTRUCT: {avg_instruct:.1f} tok/s")

            if avg_instruct > avg_base:
                diff = ((avg_instruct / avg_base) - 1) * 100
                print(f"✨ INSTRUCT es {diff:.1f}% más rápido!")

        print("="*60 + "\n")

if __name__ == "__main__":
    main()
