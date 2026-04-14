# Create the ZenAPI key
```bash
WXD_USERNAME='ibmlhadmin'
WXD_ACCESS_TOKEN=$(
  curl --location -k 'https://localhost:6443/lakehouse/api/v3/auth/authenticate' \
    --header 'Content-Type: application/json' \
    --data '{
      "username": "ibmlhadmin",
      "password": "password",
      "instance_id": "0000-0000-0000-0000",
      "instance_name": ""
    }' | jq -r '.access_token'
)
echo "$WXD_USERNAME:$WXD_ACCESS_TOKEN" | base64 -w 0 && echo
```
Use as: `"spark.hadoop.wxd.apikey": "ZenApiKey <key>"`

# Test if Spark is correctly working
Upload file ./health_check.py to Minio path /iceberg-bucket/system.
Then create a new application using the console with the following payload:
```json
{
  "application_details": {
    "application": "s3a://iceberg-bucket/system/health_check.py",
    "conf": {
      "spark.hadoop.fs.s3a.bucket.iceberg-bucket.access.key": "dummyvalue",
      "spark.hadoop.fs.s3a.bucket.iceberg-bucket.secret.key": "dummyvalue",
      "spark.hadoop.fs.s3a.bucket.iceberg-bucket.aws.credentials.provider": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
    }
  },
  "deploy_mode": "local"
}
```