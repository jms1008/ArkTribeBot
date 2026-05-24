"""Paquete K4Ultra — radar pasivo de jugadores conectados.

Este paquete sustituye al antiguo módulo monolítico ``cogs/k4ultra.py``.
Submódulos:

- ``cog``: clase principal ``K4Ultra`` con loops de recogida y comandos slash.
- ``ui``: Views/Modals (anteriormente ``cogs/k4ultra_ui.py``).

Re-exporta los símbolos públicos para que código externo siga usando
``from cogs.k4ultra import K4Ultra, K4UltraView`` sin cambios.
"""

from cogs.k4ultra.cog import K4Ultra, setup
from cogs.k4ultra.ui import K4UltraView

__all__ = ["K4Ultra", "K4UltraView", "setup"]
