import time
import asyncio
import prometheus_client
from prometheus_client import Gauge, start_http_server
import aiohttp
import os

# Remove Python default measurements from registry
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)

# List of URLs to scrape
MONGOSHAKE_SCRAPE_URL = os.environ.get(
    "MONGOSHAKE_SCRAPE_URL", "http://localhost:9100/repl"
).split(",")
# Scrape interval
MONGOSHAKE_SCRAPE_INTERVAL = int(os.environ.get("MONGOSHAKE_SCRAPE_INTERVAL", 10))

# Prometheus metric names
metric_prefix = "mongoshake"
prom_metrics = {
    "logs_get": Gauge(
        metric_prefix + "_logs_get", "Number of logs (get)", ["replset", "url"]
    ),
    "logs_repl": Gauge(
        metric_prefix + "_logs_repl", "Number of logs (repl)", ["replset", "url"]
    ),
    "logs_success": Gauge(
        metric_prefix + "_logs_success", "Number of successful logs", ["replset", "url"]
    ),
    "tps": Gauge(metric_prefix + "_tps", "Transactions per second", ["replset", "url"]),
    "replication_latency": Gauge(
        metric_prefix + "_replication_latency",
        "Replication_latency in seconds",
        ["replset", "url"],
    ),
    "lsn_unix": Gauge(
        metric_prefix + "_lsn_seconds",
        "unix time in Log Sequence Number",
        ["replset", "url"],
    ),
    "lsn_ack_unix": Gauge(
        metric_prefix + "_lsn_ack_seconds",
        "unix time in Acked Log Sequence Number",
        ["replset", "url"],
    ),
    "lsn_ckpt_unix": Gauge(
        metric_prefix + "_lsn_ckpt_seconds",
        "unix time in checkpointed Log Sequence Number",
        ["replset", "url"],
    ),
}


# Fetch url data
async def fetch_metrics(url, prom_metrics):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"Accept": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    update_prometheus_metrics(data, prom_metrics, url)
                else:
                    print(f"Failed to fetch data from {url}: {response.status}")
    except Exception as err:
        print(err, url)


# Print metrics in webserver
def update_prometheus_metrics(data, prom_metrics, url):
    # Custom metrics
    data_copy = data
    replset = data_copy["replset"]
    lsn_ack_ts = int(data_copy["lsn_ack"]["unix"])
    lsn_ckpt_ts = int(data_copy["lsn_ack"]["unix"])
    lsn_ts = int(data_copy["lsn"]["unix"])
    data_copy["replication_latency"] = lsn_ts - lsn_ack_ts
    data_copy["lsn_unix"] = lsn_ts
    data_copy["lsn_ack_unix"] = lsn_ack_ts
    data_copy["lsn_ckpt_unix"] = lsn_ckpt_ts

    # Set metrics
    for key, value in prom_metrics.items():
        value.labels(replset, url).set(data_copy[key])


async def main():
    # Start Prometheus HTTP server
    start_http_server(8000)

    # Start app
    while True:
        await asyncio.gather(
            *[fetch_metrics(url, prom_metrics) for url in MONGOSHAKE_SCRAPE_URL]
        )

        # Wait for 5 scrape interval
        await asyncio.sleep(MONGOSHAKE_SCRAPE_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt. Exiting.")
