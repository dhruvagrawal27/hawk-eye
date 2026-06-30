# --- network module outputs --------------------------------------------------
output "vpc_id" {
  description = "VPC id."
  value       = aws_vpc.main.id
}

output "data_subnet_ids" {
  description = "Private DATA subnet ids (MSK/ElastiCache/RDS)."
  value       = aws_subnet.data[*].id
}

output "compute_subnet_ids" {
  description = "Private COMPUTE subnet ids (Flink/EC2/MWAA)."
  value       = aws_subnet.compute[*].id
}

output "public_subnet_ids" {
  description = "PUBLIC subnet ids (ALB only)."
  value       = aws_subnet.public[*].id
}

output "alb_sg_id" {
  description = "ALB security group id."
  value       = aws_security_group.alb.id
}

output "compute_sg_id" {
  description = "Compute security group id."
  value       = aws_security_group.compute.id
}

output "data_sg_id" {
  description = "Data security group id."
  value       = aws_security_group.data.id
}

output "nat_gateway_id" {
  description = "NAT gateway id (the single controlled egress chokepoint)."
  value       = aws_nat_gateway.nat[0].id
}
