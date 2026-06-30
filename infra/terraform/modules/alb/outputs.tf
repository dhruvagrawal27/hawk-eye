# --- alb module outputs ------------------------------------------------------
output "alb_arn" {
  description = "ALB ARN (consumed by the security module for WAF association)."
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "Public DNS name of the ALB (the only public ingress)."
  value       = aws_lb.main.dns_name
}

output "backend_target_group_arn" {
  description = "Backend target group ARN."
  value       = aws_lb_target_group.backend.arn
}
