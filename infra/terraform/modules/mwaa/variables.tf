# --- mwaa module inputs ------------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "subnet_ids" {
  description = "Private COMPUTE subnet ids (MWAA uses exactly 2)."
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "Compute-tier security group id."
  type        = string
  default     = null
}

variable "execution_role_arn" {
  description = "MWAA execution role ARN (from iam module)."
  type        = string
  default     = null
}

variable "source_bucket_arn" {
  description = "S3 bucket ARN holding DAGs (the artifacts bucket)."
  type        = string
  default     = null
}

variable "dag_s3_path" {
  description = "Key prefix within the source bucket for DAGs."
  type        = string
  default     = "airflow/dags"
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for environment encryption."
  type        = string
  default     = null
}

variable "airflow_version" {
  description = "MWAA-supported Airflow version (BOM pin family 2.10.x)."
  type        = string
  default     = "2.10.3"
}

variable "environment_class" {
  description = "MWAA environment class (cost-conscious pilot, Part 26.3)."
  type        = string
  default     = "mw1.small"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
