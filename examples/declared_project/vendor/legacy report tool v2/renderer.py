"""Renders rows the way the legacy tool always has."""


def render(rows):
    width = max(len(row) for row in rows)
    return "\n".join(f"| {row:<{width}} |" for row in rows)
