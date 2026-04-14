# Global Parcel Hybrid Lakehouse Demo

This repository is a follow-along demo for running **IBM watsonx.data** locally and walking through a realistic Global Parcel use case:

- ingest shipping history into Iceberg
- query operational insights with Presto
- federate that data with external PostgreSQL fuel surcharge data

Official watsonx.data installation docs: [Installing watsonx.data](https://www.ibm.com/docs/en/watsonxdata/standard/2.3.x?topic=version-installing)

![Global Parcel Lakehouse Journey](assets/global-parcel-lakehouse-journey.png)

## Use Case

Global Parcel needs better control over shipping analytics while meeting data sovereignty requirements.  
The team keeps historical parcel events in lakehouse storage and combines them with live fuel surcharge data from PostgreSQL to calculate real invoice impact.

You will reproduce that flow end-to-end on a local Kind cluster.

## Prerequisites

- Linux host with Docker Engine
- `kubectl`
- `helm`
- `kind`
- Python (for data generation scripts)
- `values-secret.yaml` prepared for `watsonx.data-developer-edition-installer`

## 1) Install Tooling

### Install kubectl
```bash
sudo dnf install kubernetes-client
```

### Install Helm
```bash
sudo dnf install helm
```

### Install Kind
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.31.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

### Set SELinux permissive (if required for your setup)
```bash
sudo setenforce 0
```

## 2) Create and Validate Cluster

### Create Kind cluster
```bash
kind create cluster --name wxd
```

### Check Kubernetes readiness
```bash
watch kubectl get pods -n kube-system -o wide
```

### Optional host readiness check
```bash
./host_readiness.sh
```

## 3) Install watsonx.data

```bash
cd watsonx.data-developer-edition-installer
helm dependency update
helm upgrade --install wxd . \
  -f values.yaml \
  -f values-secret.yaml \
  --namespace wxd \
  --create-namespace \
  --timeout 10m
```

### Check watsonx.data readiness
```bash
watch kubectl get pods -n wxd
```

### Port-forward required services
```bash
nohup kubectl port-forward -n wxd service/lhconsole-ui-svc 6443:443 --address 0.0.0.0 2>&1 &
nohup kubectl port-forward -n wxd service/ibm-lh-minio-svc 9001:9001 --address 0.0.0.0 2>&1 &
nohup kubectl port-forward -n wxd service/ibm-lh-mds-thrift-svc 8381:8381 --address 0.0.0.0 2>&1 &
```

## 4) Follow-Along: Shipping History

### Generate sample shipping history
```bash
python 01_generate_shipping_history.py
```

### Load CSV into watsonx.data
1. Open `https://localhost:6443/` and sign in (`ibmlhadmin` / `password`).
2. Go to `Infrastructure manager` -> `Add component`.
3. Select `IBM Spark`, click `Next`.
4. Set display name (for example `spark-01`) and associate catalog `iceberg_bucket`.
5. Go to `Data manager` -> `iceberg_data` -> menu (`...`) -> `Create schema`.
6. Name schema `shipping`.
7. Under `iceberg_bucket`, use menu (`...`) -> `Create table from ...`.
8. Select generated `shipping_history.csv`.
9. Set target table name `shipping`, pick Spark engine, click `Done`.

### Query delayed shipments
In `Query workspace`, run:

```sql
SELECT origin_city, COUNT(*) AS volume, AVG(shipping_cost) AS avg_cost
FROM iceberg_data.shipping.shipping
WHERE status = 'Delayed'
GROUP BY origin_city
ORDER BY volume DESC;
```

## 5) Follow-Along: Add Fuel Surcharge Data (PostgreSQL)

### Start PostgreSQL
```bash
docker run --name shipping-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=shipping_ops \
  -p 5432:5432 \
  -d postgres:latest
```

Get a connection string usable from watsonx.data:

```bash
printf 'postgresql://postgres:postgres@%s:5432/shipping_ops\n' "$(hostname -I | awk '{print $1}')"
```

### Generate and load fuel data
```bash
python 06_generate_fuel_data.py
```

### Add PostgreSQL as a federated source
1. Go to `Infrastructure manager` -> `Add component`.
2. Select `PostgreSQL`.
3. Enter:
   - Display name: `Fuel surge pricing`
   - Database name: `shipping_ops`
   - Hostname: your host IP from command above
   - Port: `5432`
   - Username: `postgres`
   - Password: `postgres`
4. Click `Test connection`.
5. Enable `Associate catalog`.
6. Name catalog `fuel_index`.
7. Click `Create`.

### Associate catalog with Presto
In `Infrastructure manager`, hover catalog -> `Manage associations` -> select Presto -> `Save and restart engine`.

### Query combined shipping + fuel surcharge impact
```sql
SELECT
  s.package_id,
  s.region,
  s.shipping_cost AS base_rate,
  f.fuel_surcharge,
  (s.shipping_cost + f.fuel_surcharge) AS total_invoice
FROM iceberg_data.shipping.shipping s
JOIN fuel_prices.public.fuel_index f ON s.region = f.region
LIMIT 10;
```

## Operations

### Pause or resume local cluster
```bash
docker stop wxd-control-plane
docker start wxd-control-plane
```

### Tear down everything
```bash
kind delete cluster --name wxd
docker system prune -a
```