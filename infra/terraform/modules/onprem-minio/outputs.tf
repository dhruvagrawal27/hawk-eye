# --- onprem-minio module outputs ----------------------------------
output "component" {
  description = "Self-hosted MinIO component identity (on-prem target)."
  value = {
    component = "MinIO (S3 API, object-lock/WORM)"
    image     = "minio/minio:RELEASE.2024-12-18T13-15-44Z"
    swaps     = "S3 -> MinIO"
  }
}
