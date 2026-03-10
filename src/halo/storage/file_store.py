"""File-based store - inspirado en Claude Code.

Por qué file-based en lugar de SQLite:
- Legibilidad: cat flow.json
- Multi-agente: Cualquier proceso lee/escribe
- Versionable: Git-friendly
- Debugging: Editor de texto
- Monitoreo externo: inotify, tail -f
- Backup: cp -r
- Corrupción: Un archivo, no toda la DB
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

try:
    from filelock import FileLock
except ImportError:
    # Fallback si filelock no está instalado
    class FileLock:
        def __init__(self, path: str):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass


class FileStore:
    """File-based store - transparente, multi-agente, legible.

    Estructura:
    /var/halo/
    ├── soul/                  # Nivel 5: El Alma
    ├── environment/           # Nivel 4: Contexto Ambiental
    ├── sessions/              # Nivel 3: Sesiones
    ├── flows/                 # Nivel 2: Flujos
    ├── learning/              # Sistema de aprendizaje
    ├── context/               # Contexto semántico
    └── logs/                  # Observabilidad (JSONL)
    """

    def __init__(self, base_path: str = "/var/halo"):
        """
        Args:
            base_path: Directorio base para almacenamiento.
                      Para testing, usar un directorio temporal.
        """
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def write(self, collection: str, key: str, data: dict) -> Path:
        """Escribe un documento JSON.

        Args:
            collection: Colección (ej: "flows/active", "learning/candidates")
            key: Identificador único
            data: Datos a escribir

        Returns:
            Path del archivo creado
        """
        path = self.base / collection / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(f"{path}.lock"):
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        return path

    def read(self, collection: str, key: str) -> Optional[dict]:
        """Lee un documento JSON.

        Args:
            collection: Colección
            key: Identificador

        Returns:
            Dict con los datos, o None si no existe
        """
        path = self.base / collection / f"{key}.json"
        if not path.exists():
            return None

        return json.loads(path.read_text(encoding="utf-8"))

    def list_keys(self, collection: str) -> list[str]:
        """Lista todas las keys en una colección.

        Args:
            collection: Colección

        Returns:
            Lista de keys (sin extensión .json)
        """
        path = self.base / collection
        if not path.exists():
            return []

        return [f.stem for f in path.glob("*.json")]

    def delete(self, collection: str, key: str) -> bool:
        """Elimina un documento.

        Args:
            collection: Colección
            key: Identificador

        Returns:
            True si se eliminó, False si no existía
        """
        path = self.base / collection / f"{key}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def append_log(self, category: str, entry: dict) -> None:
        """Append-only log (JSONL).

        Args:
            category: Categoría del log (ej: "telemetry", "classification")
            entry: Entrada a agregar
        """
        # Logs organizados por fecha
        path = self.base / "logs" / f"{category}_{date.today()}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(f"{path}.lock"), open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_logs(self, category: str, date_str: Optional[str] = None) -> list[dict]:
        """Lee logs de una categoría.

        Args:
            category: Categoría del log
            date_str: Fecha en formato YYYY-MM-DD (default: hoy)

        Returns:
            Lista de entradas del log
        """
        if date_str is None:
            date_str = str(date.today())

        path = self.base / "logs" / f"{category}_{date_str}.jsonl"
        if not path.exists():
            return []

        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def read_manifest(self) -> str:
        """Lee el manifest.md (el alma de Halo).

        Returns:
            Contenido del manifest, o string vacío si no existe
        """
        path = self.base / "soul" / "manifest.md"
        if not path.exists():
            return ""

        return path.read_text(encoding="utf-8")

    def write_manifest(self, content: str) -> Path:
        """Escribe el manifest.md.

        Args:
            content: Contenido del manifest

        Returns:
            Path del archivo
        """
        path = self.base / "soul" / "manifest.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def move(self, from_collection: str, to_collection: str, key: str) -> bool:
        """Mueve un documento de una colección a otra.

        Útil para mover flows de active/ a completed/.

        Args:
            from_collection: Colección origen
            to_collection: Colección destino
            key: Identificador

        Returns:
            True si se movió, False si no existía
        """
        data = self.read(from_collection, key)
        if data is None:
            return False

        self.write(to_collection, key, data)
        self.delete(from_collection, key)
        return True
