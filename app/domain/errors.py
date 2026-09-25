"""Provider-independent failures crossing the application boundary."""


class GeocodingError(RuntimeError):
    """An external address could not be resolved."""


class CatalogueError(RuntimeError):
    """The vehicle reference catalogue cannot be read safely."""


class RoutingError(RuntimeError):
    """An external road route could not be produced."""


class WorldCatalogueError(CatalogueError):
    """World reference data is unavailable or incompatible."""


class PersistenceError(RuntimeError):
    """The persistence adapter could not safely read or write state."""


class UnsupportedGameSchema(PersistenceError):
    """Normal runtime refuses an old, incomplete or unknown state schema."""


class DuplicateAccountError(ValueError):
    """An account name is already assigned, including registration races."""


class AmbiguousWorldReference(ValueError):
    """A name identifies multiple references within the selected scope."""


class UnresolvedVehicleModel(ValueError):
    """An owned vehicle requires an explicit catalogue model assignment."""
