"""
Health check driver script. stdout from this file (including print below) is emitted by the
Spark *driver* process. With cluster-style submit from the Spark master, that is the
spark-master pod — not spark-worker. Worker pod logs only show the Worker JVM and executor
streams (e.g. EXECUTOR-0), so you will not see this line when tailing a worker.
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("HealthCheck").getOrCreate()
# This forces an actual distributed operation (parallelize)
# flush=True: under spark-submit stdout is often not a TTY, so Python may buffer prints
# until exit unless flushed (or run with python -u / PYTHONUNBUFFERED=1).
print(f"Spark Version: {spark.version} - Status: OK", flush=True)
spark.range(1, 10).count()
