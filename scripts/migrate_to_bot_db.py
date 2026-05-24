"""Script one-shot para migrar bloques ``async with aiosqlite.connect(...)``
al patrón ``db = self.bot.db``.

Reglas:
- Detecta líneas con ``async with aiosqlite.connect(self.bot.db_name) as <name>:``
  (también ``bot.db_name`` sin ``self``).
- La siguiente línea con ``<name>.row_factory = aiosqlite.Row`` se borra.
- Reemplaza la línea del ``async with`` por ``<name> = self.bot.db`` (o ``bot.db``).
- Desindenta 4 espacios todo el bloque hasta que la indentación caiga
  al nivel del ``async with`` original.

No toca:
- Bloques que abren conexión a un fichero distinto de ``bot.db_name``.
- Helpers públicos con fallback explícito (los respeta porque no usan el
  patrón con ``self.bot.db_name`` directo o están dentro de un ``else``).

Uso: ``python scripts/migrate_to_bot_db.py <archivo.py> [...]``
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ASYNC_WITH_RE = re.compile(
    r"^(?P<indent>\s*)async with aiosqlite\.connect\((?P<bot>self\.bot|bot)\.db_name\) as (?P<name>\w+):\s*$"
)


def migrate(source: str) -> tuple[str, int]:
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    migrated = 0

    while i < len(lines):
        line = lines[i]
        m = ASYNC_WITH_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue

        indent = m.group("indent")
        bot_ref = m.group("bot")
        var = m.group("name")

        # Línea de reemplazo (misma indentación que el async with original).
        out.append(f"{indent}{var} = {bot_ref}.db\n")

        # Siguiente línea: si es "var.row_factory = aiosqlite.Row", se descarta.
        j = i + 1
        row_factory_line = f"{indent}    {var}.row_factory = aiosqlite.Row"
        if j < len(lines) and lines[j].rstrip() == row_factory_line:
            j += 1

        # Procesar el cuerpo: todo lo que esté indentado al menos `len(indent)+4`
        # hasta que aparezca una línea con indentación <= `len(indent)`.
        body_min_indent = len(indent) + 4
        body_indent_str = " " * 4  # cantidad a desindentar
        while j < len(lines):
            body_line = lines[j]
            # Línea vacía: no cambia.
            if body_line.strip() == "":
                out.append(body_line)
                j += 1
                continue
            current_indent = len(body_line) - len(body_line.lstrip(" "))
            if current_indent < body_min_indent:
                break
            # Desindentar 4 espacios.
            out.append(body_line[len(body_indent_str):])
            j += 1

        migrated += 1
        i = j

    return "".join(out), migrated


def main(argv: list[str]) -> int:
    total = 0
    for arg in argv[1:]:
        path = Path(arg)
        src = path.read_text(encoding="utf-8")
        new_src, n = migrate(src)
        if n:
            path.write_text(new_src, encoding="utf-8")
            total += n
            print(f"{arg}: {n} bloques migrados")
        else:
            print(f"{arg}: sin cambios")
    print(f"TOTAL: {total} bloques")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
