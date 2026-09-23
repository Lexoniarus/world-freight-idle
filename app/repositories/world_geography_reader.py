"""Read shared geographical reference entities from normalized tables."""

import sqlite3

from app.domain.geography import City, Country


def read_countries(connection: sqlite3.Connection) -> dict[str, Country]:
    """Load countries by their stable reference code."""
    return {
        row["code"]: Country(row["code"], row["name"])
        for row in connection.execute("SELECT * FROM countries ORDER BY code")
    }


def read_cities(
    connection: sqlite3.Connection, countries: dict[str, Country]
) -> dict[str, City]:
    """Compose shared country values into permanently identified cities."""
    return {
        row["city_uid"]: City(
            row["city_uid"],
            row["name"],
            countries[row["country_code"]],
            row["region"],
        )
        for row in connection.execute("SELECT * FROM cities ORDER BY city_uid")
    }
