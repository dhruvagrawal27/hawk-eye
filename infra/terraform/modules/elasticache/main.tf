# =============================================================================
# Hawk-Eye — ElastiCache module (Redis online feature store / cache) [SCAFFOLD]
# Purpose : Sub-ms online feature serving + cache. Private, encrypted in transit
#           and at rest.
# Blueprint: Part 26.1 (Online feature store / cache → ElastiCache for Redis), 26.4 (→ Redis)
# Task     : PLATFORM-7 (elasticache)
# =============================================================================

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name_prefix}-redis-subnets"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

# SCAFFOLD: Redis 7.4.x (BOM pin 7.4.1). Replication group with one replica for HA;
# encryption in transit + at rest on. Private subnets only.
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.name_prefix}-redis"
  description          = "${var.name_prefix} online feature store / cache"
  engine               = "redis"
  engine_version       = "7.4" # BOM pin family
  node_type            = var.node_type
  num_cache_clusters   = 2 # primary + 1 replica (multi-AZ HA, Part 30)
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.security_group_id]

  automatic_failover_enabled = true
  multi_az_enabled           = true

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = var.tags
}
