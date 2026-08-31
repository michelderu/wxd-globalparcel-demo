"""Shared StreamHouse runtime configuration.

Apache Kafka is the capture bus (localhost:9092). The transform writes IBM
engines (Cassandra, OpenSearch) and Kafka topics that Tableflow materializes
for watsonx.data.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("STREAMHOUSE_DATA", REPO_ROOT / "data"))
CATALOG_DB = DATA_DIR / "catalog.db"
WAREHOUSE_DIR = DATA_DIR / "warehouse"

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")

CASSANDRA_HOST = os.environ.get("CASSANDRA_HOST", "127.0.0.1")
CASSANDRA_PORT = int(os.environ.get("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.environ.get("CASSANDRA_KEYSPACE", "globalparcel_ops")
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "parcel-events-live")

TOPIC_EVENTS = "parcel.events"
TOPIC_SURCHARGE = "fuel.surcharge"
TOPIC_ENRICHED = "parcel.events.enriched"
TOPIC_CURRENT = "parcel.current"
TOPIC_ALERTS = "ops.sla.alerts"

ICEBERG_NAMESPACE = "globalparcel"
TABLE_EVENTS = f"{ICEBERG_NAMESPACE}.parcel_events"
TABLE_CURRENT = f"{ICEBERG_NAMESPACE}.parcel_current"
TABLE_SURCHARGE = f"{ICEBERG_NAMESPACE}.fuel_surcharge"
TABLE_ALERTS = f"{ICEBERG_NAMESPACE}.sla_alerts"

# Region list prices before the live fuel surcharge stream is applied.
BASE_RATE_BY_REGION = {
    "EU-WEST": 18.40,
    "EU-NORTH": 17.10,
    "EU-SOUTH": 16.80,
    "NA-EAST": 21.50,
    "NA-CENTRAL": 20.20,
    "SA-EAST": 24.90,
    "MEA": 22.70,
    "APAC-SOUTH": 19.80,
    "APAC-SE": 19.10,
    "APAC-EAST": 20.40,
    "APAC-OCEANIA": 26.30,
}

DEFAULT_SURCHARGE = {
    "EU-WEST": 6.10,
    "EU-NORTH": 5.50,
    "EU-SOUTH": 4.20,
    "NA-EAST": 7.40,
    "NA-CENTRAL": 6.80,
    "SA-EAST": 8.10,
    "MEA": 7.90,
    "APAC-SOUTH": 6.40,
    "APAC-SE": 5.90,
    "APAC-EAST": 6.20,
    "APAC-OCEANIA": 8.60,
}
