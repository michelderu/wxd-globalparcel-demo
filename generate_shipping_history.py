'''Generate synthetic shipping_history.csv / .parquet for demo purposes.'''

import argparse
import csv
import random
from pathlib import Path
from typing import Iterator

import pandas as pd

EUROPEAN_CITIES = [
    # Western & Central Europe
    "Amsterdam", "Rotterdam", "Brussels", "Antwerp", "Paris", "Lyon", "Marseille",
    "Berlin", "Hamburg", "Munich", "Frankfurt", "Cologne", "Vienna", "Zurich",
    "Geneva", "Basel", "Luxembourg City",
    # Southern Europe
    "Madrid", "Barcelona", "Valencia", "Seville", "Lisbon", "Porto", "Rome",
    "Milan", "Naples", "Turin", "Florence", "Athens", "Thessaloniki",
    # Northern Europe
    "London", "Manchester", "Birmingham", "Edinburgh", "Dublin", "Cork",
    "Stockholm", "Gothenburg", "Oslo", "Bergen", "Copenhagen", "Aarhus",
    "Helsinki", "Tampere",
    # Eastern & Baltic
    "Warsaw", "Kraków", "Gdańsk", "Prague", "Brno", "Budapest", "Debrecen",
    "Bucharest", "Cluj-Napoca", "Sofia", "Plovdiv", "Zagreb", "Split",
    "Ljubljana", "Bratislava", "Košice", "Vilnius", "Kaunas", "Riga",
    "Tallinn", "Tartu",
    # Southeastern Europe
    "Belgrade", "Novi Sad", "Sarajevo", "Skopje", "Tirana", "Podgorica",
    "Istanbul", "Izmir", "Ankara",
]

# Aligns with 06_generate_fuel_data.py / fuel_index.region for hybrid joins (EU_NORTH, EU_SOUTH, EU_WEST).

# Western & Central Europe + UK/IE — EU_WEST
_CITIES_EU_WEST = frozenset(
    {
        "Amsterdam",
        "Rotterdam",
        "Brussels",
        "Antwerp",
        "Paris",
        "Lyon",
        "Marseille",
        "Berlin",
        "Hamburg",
        "Munich",
        "Frankfurt",
        "Cologne",
        "Vienna",
        "Zurich",
        "Geneva",
        "Basel",
        "Luxembourg City",
        "London",
        "Manchester",
        "Birmingham",
        "Edinburgh",
        "Dublin",
        "Cork",
    }
)
# Iberia, Italy, Greece — EU_SOUTH
_CITIES_EU_SOUTH = frozenset(
    {
        "Madrid",
        "Barcelona",
        "Valencia",
        "Seville",
        "Lisbon",
        "Porto",
        "Rome",
        "Milan",
        "Naples",
        "Turin",
        "Florence",
        "Athens",
        "Thessaloniki",
    }
)

# Nordics, Eastern Europe, Baltics, Balkans, Turkey — EU_NORTH (all remaining cities)
_CITIES_EU_NORTH = frozenset(c for c in EUROPEAN_CITIES if c not in _CITIES_EU_WEST and c not in _CITIES_EU_SOUTH)


def region_for_city(city: str) -> str:
    """Map a European city to EU_NORTH / EU_SOUTH / EU_WEST (matches fuel_index)."""
    if city in _CITIES_EU_WEST:
        return "EU_WEST"
    if city in _CITIES_EU_SOUTH:
        return "EU_SOUTH"
    if city in _CITIES_EU_NORTH:
        return "EU_NORTH"
    raise ValueError(f"Unknown city for region mapping: {city!r}")


assert _CITIES_EU_WEST.isdisjoint(_CITIES_EU_SOUTH)
assert set(EUROPEAN_CITIES) == _CITIES_EU_WEST | _CITIES_EU_SOUTH | _CITIES_EU_NORTH

STATUSES = ["Delivered", "In-Transit", "Delayed"]

OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = OUTPUT_DIR / "shipping_history.csv"
OUTPUT_PARQUET = OUTPUT_DIR / "shipping_history.parquet"
NUM_ROWS = 10_000
RNG = random.Random(42)

FIELDNAMES = [
    "package_id",
    "origin_city",
    "destination_city",
    "region",
    "status",
    "weight_kg",
    "shipping_cost",
]


def random_city(exclude: str | None = None) -> str:
    c = RNG.choice(EUROPEAN_CITIES)
    while exclude is not None and c == exclude:
        c = RNG.choice(EUROPEAN_CITIES)
    return c


def iter_shipping_rows() -> Iterator[dict[str, object]]:
    """Yield shipping rows with a fixed RNG sequence (seed 42) each time."""
    RNG.seed(42)
    for i in range(1, NUM_ROWS + 1):
        origin = random_city()
        dest = random_city(exclude=origin)
        weight = round(RNG.uniform(0.25, 75.0), 2)
        base = 4.5 + weight * 0.85 + RNG.uniform(0, 120)
        shipping_cost = round(base, 2)
        yield {
            "package_id": f"PKG-{i:06d}",
            "origin_city": origin,
            "destination_city": dest,
            "region": region_for_city(dest),
            "status": RNG.choice(STATUSES),
            "weight_kg": weight,
            "shipping_cost": shipping_cost,
        }


def generate_shipping_history_csv(path: Path | None = None) -> Path:
    out = path or OUTPUT_CSV
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in iter_shipping_rows():
            writer.writerow(row)
    print(f"Wrote {NUM_ROWS} rows to {out}")
    return out


def generate_shipping_history_parquet(path: Path | None = None) -> Path:
    out = path or OUTPUT_PARQUET
    df = pd.DataFrame(iter_shipping_rows(), columns=FIELDNAMES)
    df.to_parquet(out, index=False)
    print(f"Wrote {NUM_ROWS} rows to {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("csv", "parquet", "both"),
        default="csv",
        help="Output format (default: csv)",
    )
    args = parser.parse_args()
    if args.format in ("csv", "both"):
        generate_shipping_history_csv()
    if args.format in ("parquet", "both"):
        generate_shipping_history_parquet()


if __name__ == "__main__":
    main()
