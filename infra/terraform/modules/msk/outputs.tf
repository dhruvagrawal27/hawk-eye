# --- msk module outputs ------------------------------------------------------
output "cluster_arn" {
  description = "MSK cluster ARN."
  value       = aws_msk_cluster.main.arn
}

output "bootstrap_brokers_tls" {
  description = "TLS bootstrap broker connection string."
  value       = aws_msk_cluster.main.bootstrap_brokers_tls
}

output "zookeeper_connect" {
  description = "ZooKeeper / metadata connect string."
  value       = aws_msk_cluster.main.zookeeper_connect_string
}
