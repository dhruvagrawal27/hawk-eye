# --- lightsail-network module outputs ----------------------------------------
output "static_ip_name" {
  description = "Lightsail static IP name."
  value       = aws_lightsail_static_ip.demo.name
}

output "static_ip_address" {
  description = "Lightsail static IP address (the stable demo endpoint)."
  value       = aws_lightsail_static_ip.demo.ip_address
}
