#!/bin/bash
# Script para configurar Gemini API key desde .keys o prompt

set -e

echo "🔧 Configurando Gemini API para Halo"
echo ""

# Check if .keys file exists
if [ -f ".keys" ]; then
    echo "✅ Encontrado archivo .keys"

    # Try to extract GEMINI_API_KEY from .keys
    if grep -q "GEMINI_API_KEY" .keys; then
        echo "✅ GEMINI_API_KEY encontrada en .keys"

        # Export to .env
        if [ ! -f ".env" ]; then
            echo "# Halo Configuration" > .env
        fi

        # Extract and add to .env
        GEMINI_KEY=$(grep "GEMINI_API_KEY" .keys | cut -d'=' -f2 | tr -d ' "')

        if grep -q "GEMINI_API_KEY" .env; then
            # Replace existing
            sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$GEMINI_KEY/" .env
            echo "✅ GEMINI_API_KEY actualizada en .env"
        else
            # Add new
            echo "GEMINI_API_KEY=$GEMINI_KEY" >> .env
            echo "✅ GEMINI_API_KEY agregada a .env"
        fi
    else
        echo "⚠️  GEMINI_API_KEY no encontrada en .keys"
        echo "   Agrega esta línea a .keys:"
        echo "   GEMINI_API_KEY=tu_api_key_aqui"
        exit 1
    fi
else
    echo "⚠️  Archivo .keys no encontrado"
    echo ""
    echo "Opciones:"
    echo "1. Crear archivo .keys con:"
    echo "   echo 'GEMINI_API_KEY=tu_api_key_aqui' > .keys"
    echo ""
    echo "2. O agregar directamente a .env:"
    echo "   echo 'GEMINI_API_KEY=tu_api_key_aqui' >> .env"
    echo ""
    echo "3. Obtener API key en: https://aistudio.google.com/apikey"
    exit 1
fi

echo ""
echo "🎉 Configuración completa!"
echo ""
echo "Para verificar:"
echo "  source .env"
echo "  echo \$GEMINI_API_KEY"
echo ""
echo "Para testear Gemini:"
echo "  uv run python test/test_gemini_classifier.py"
