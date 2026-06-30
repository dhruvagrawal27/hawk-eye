# =============================================================================
# Hawk-Eye — ALB module (the ONLY public ingress) [SCAFFOLD]
# Purpose : Application Load Balancer in the public subnet; HTTPS listener that
#           fronts the backend/serving/dashboard. The single internet entry point.
# Blueprint: Part 26.1 (App/API behind ALB), Part 26.2 (only the ALB is public)
# Task     : PLATFORM-7 (alb)
# =============================================================================

# SCAFFOLD: internet-facing ALB. HTTP->HTTPS redirect + an HTTPS listener with a
# fixed-response default (real target groups wired at apply time). WAF is attached
# by the `security` module.
resource "aws_lb" "main" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_id]
  subnets            = var.public_subnet_ids

  drop_invalid_header_fields = true # hardening
  enable_deletion_protection = true

  tags = var.tags
}

# Default target group (backend API :8000). Targets registered at apply time.
resource "aws_lb_target_group" "backend" {
  name        = "${var.name_prefix}-tg-backend"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/healthz"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

# HTTP listener -> redirect to HTTPS (no plaintext served).
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS listener. ACM cert ARN supplied at apply time; default action is a guarded
# fixed response until target groups are attached.
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}
