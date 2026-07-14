from __future__ import annotations

from platform_db.api import app
from web_collab_prototype.app import app as legacy_prototype_app


def _is_a111_compatibility_route(path: str) -> bool:
    return path in {"/static", "/quota-a111"} or path.startswith("/api/quota-a111")


# The authenticated platform remains authoritative. Only the established A111
# compatibility surface is composed from the legacy prototype.
existing_paths = {getattr(route, "path", "") for route in app.router.routes}
for route in legacy_prototype_app.router.routes:
    path = getattr(route, "path", "")
    if _is_a111_compatibility_route(path) and path not in existing_paths:
        app.router.routes.append(route)
        existing_paths.add(path)

app.state.runtime_entrypoint = "platform_db.web_app:app"
app.state.legacy_prototype_policy = "quota-a111 compatibility only"
