from typing import List
from orchestrator.models import ComponentSpec


def print_dry_run(ordered_components: List[ComponentSpec], templates: List[str]) -> None:
    """Print ordered DAG as a tree without executing anything."""
    print("=== DRY RUN — Pipeline Plan ===")
    print()
    for i, c in enumerate(ordered_components, 1):
        t = c.template or "(core)"
        deps = ", ".join(c.depends_on) or "(none)"
        print(f"  {i}. {c.id} [{c.agent}]")
        print(f"     template={t}  depends_on=[{deps}]")
    print()
    print(f"  Total: {len(ordered_components)} components")
    if templates:
        print(f"  Available templates: {', '.join(templates)}")
    print()
