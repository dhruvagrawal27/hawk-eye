# --- lightsail-instances module outputs --------------------------------------
output "instance_name" {
  description = "Lightsail instance name running the compose stack."
  value       = aws_lightsail_instance.compose.name
}

output "instance_arn" {
  description = "Lightsail instance ARN."
  value       = aws_lightsail_instance.compose.arn
}

output "public_ip_address" {
  description = "Default (dynamic) public IP — replaced by the static IP in lightsail-network."
  value       = aws_lightsail_instance.compose.public_ip_address
}
