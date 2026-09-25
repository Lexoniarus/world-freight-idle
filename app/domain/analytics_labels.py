"""Readable current vehicle labels without historical model assertions."""

from collections import Counter


def vehicle_labels(
    names: tuple[tuple[str, str], ...], identifiers: tuple[str, ...]
) -> dict[str, str]:
    """Disambiguate display names and shorten missing-vehicle identities."""
    current = dict(names)
    counts = Counter(current.values())
    result = {}
    unique = sorted(set(identifiers))
    for identifier in unique:
        name = current.get(identifier)
        width = 8
        while any(
            other != identifier and other[:width] == identifier[:width]
            for other in unique
        ):
            width += 1
        suffix = identifier[:width]
        if name is None:
            result[identifier] = "Fahrzeug " + suffix
        else:
            result[identifier] = name + (
                " · " + suffix if counts[name] > 1 else ""
            )
    return result
