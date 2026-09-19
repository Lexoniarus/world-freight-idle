"""Provider-independent failures crossing the application boundary."""


class GeocodingError(RuntimeError):
    """An external address could not be resolved."""


class CatalogueError(RuntimeError):
    """The vehicle reference catalogue cannot be read safely."""


class RoutingError(RuntimeError):
    """An external road route could not be produced."""


class WorldCatalogueError(CatalogueError):
    """World reference data is unavailable or incompatible."""
