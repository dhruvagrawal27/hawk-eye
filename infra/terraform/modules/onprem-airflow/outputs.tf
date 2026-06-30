# --- onprem-airflow module outputs ----------------------------------
output "component" {
  description = "Self-hosted Airflow component identity (on-prem target)."
  value = {
    component = "Apache Airflow 2.10.4"
    image     = "apache/airflow:2.10.4"
    swaps     = "MWAA -> Airflow"
  }
}
