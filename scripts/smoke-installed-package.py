from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import lele_manager
from lele_manager.api import server

package_root = Path(lele_manager.__file__).resolve().parent
static_root = package_root / "gui" / "static"
gui_index = static_root / "index.html"
assets = sorted(
    path
    for path in static_root.rglob("*")
    if path.is_file()
)
frontend_assets = [
    path
    for path in assets
    if path.suffix in {".css", ".js"}
]

installed_version = version("lele-manager")

print(f"Versione installata: {installed_version}")
print(f"Package root:        {package_root}")
print(f"API module:          {Path(server.__file__).resolve()}")
print(f"FastAPI version:     {server.app.version}")
print(f"GUI index:           {gui_index}")
print(f"File GUI:            {len(assets)}")
print(f"Asset CSS/JS:        {len(frontend_assets)}")

if server.app.version != installed_version:
    raise SystemExit(
        "ERRORE: versione FastAPI diversa dal package installato."
    )

if server.GUI_DIR != static_root:
    raise SystemExit(
        "ERRORE: il server non ha risolto la GUI installata."
    )

if not gui_index.is_file():
    raise SystemExit(
        "ERRORE: index.html della GUI assente."
    )

if not frontend_assets:
    raise SystemExit(
        "ERRORE: asset CSS/JS compilati assenti."
    )

index_text = gui_index.read_text(encoding="utf-8")
if "LeLe Manager" not in index_text:
    raise SystemExit(
        "ERRORE: index.html non contiene il titolo atteso."
    )

print("OK: wheel installata con CLI, API e GUI compilata.")
