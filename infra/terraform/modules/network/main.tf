# =============================================================================
# Hawk-Eye — Network module (VPC, subnets, SGs, NACLs, allow-listed NAT) [SCAFFOLD]
# Purpose : Private-first VPC. Data + compute in PRIVATE subnets; only the ALB in
#           a PUBLIC subnet. Least-open SGs + NACLs. Egress allow-listed to the
#           NEAR AI + Groq endpoints ONLY; everything else has NO internet egress.
# Blueprint: Part 26.2 (VPC isolation, controlled LLM egress), Part 19.3 (air-gap)
# Task     : PLATFORM-7 (network)
# =============================================================================

# --- VPC ---------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

# --- Subnets -----------------------------------------------------------------
# DATA subnets (MSK, ElastiCache, RDS) — private, no route to IGW.
resource "aws_subnet" "data" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index) # 10.42.0.0/20, 10.42.16.0/20
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-data-${count.index}", tier = "data" })
}

# COMPUTE subnets (Flink, EC2 ClickHouse/serving/keycloak, MWAA) — private.
resource "aws_subnet" "compute" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4) # 10.42.64.0/20, ...
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-compute-${count.index}", tier = "compute" })
}

# PUBLIC subnet — ONLY the ALB lives here (the single public ingress).
resource "aws_subnet" "public" {
  count                   = length(var.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 8) # 10.42.128.0/20, ...
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false # ALB gets its own ENIs; instances never get public IPs
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-public-${count.index}", tier = "public" })
}

# --- Internet gateway (for the public/ALB subnet only) -----------------------
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-igw" })
}

# --- NAT gateway: the ONLY controlled egress path ----------------------------
# SCAFFOLD: a NAT gateway gives private subnets outbound. FQDN allow-listing to
# cloud-api.near.ai + api.groq.com cannot be done by the NAT itself — it is
# enforced by (a) a forward proxy / Squid with an allow-list, or (b) a
# Route53-Resolver-DNS-Firewall + managed-prefix-list at apply time. The NAT here
# is the single chokepoint; the egress SG below pins outbound to 443 + the
# allow-list. See README for the air-gap rationale.
resource "aws_eip" "nat" {
  count  = 1
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name_prefix}-nat-eip" })
}

resource "aws_nat_gateway" "nat" {
  count         = 1
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  tags          = merge(var.tags, { Name = "${var.name_prefix}-nat" })
  depends_on    = [aws_internet_gateway.igw]
}

# --- Route tables ------------------------------------------------------------
# Public RT → IGW (ALB only).
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private RT → NAT (compute subnets get controlled egress for the LLM call only).
resource "aws_route_table" "compute" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat[0].id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-compute-rt" })
}

resource "aws_route_table_association" "compute" {
  count          = length(aws_subnet.compute)
  subnet_id      = aws_subnet.compute[count.index].id
  route_table_id = aws_route_table.compute.id
}

# Data RT → NO default route (no internet egress at all — true air-gap for data tier).
resource "aws_route_table" "data" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-data-rt", egress = "none" })
}

resource "aws_route_table_association" "data" {
  count          = length(aws_subnet.data)
  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}

# --- Security groups (least-open) --------------------------------------------
# ALB SG: public 443 in, forwards to app SG only.
resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb-sg"
  description = "ALB: HTTPS in from internet; the only public ingress."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "To app/compute tier within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-alb-sg" })
}

# COMPUTE SG: intra-VPC only, plus egress to 443 (constrained by NAT + proxy).
resource "aws_security_group" "compute" {
  name        = "${var.name_prefix}-compute-sg"
  description = "Compute tier: intra-VPC only; egress 443 to allow-listed LLM endpoints via NAT/proxy."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Intra-VPC from ALB + peers"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  # NOTE: SGs are FQDN-blind. This egress permits 443 outbound; the *destination*
  # is constrained to cloud-api.near.ai + api.groq.com by the forward proxy /
  # DNS-firewall in front of the NAT (see README). No other ports leave.
  egress {
    description = "HTTPS egress (allow-listed to NEAR AI + Groq at the proxy)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Intra-VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-compute-sg" })
}

# DATA SG: intra-VPC only, NO egress to internet (true air-gap).
resource "aws_security_group" "data" {
  name        = "${var.name_prefix}-data-sg"
  description = "Data tier: intra-VPC only; NO internet egress (air-gap)."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Intra-VPC from compute tier"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "Intra-VPC only"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-data-sg" })
}

# --- NACLs (defence-in-depth, stateless) -------------------------------------
# Data subnets: allow intra-VPC, deny all else (no internet at the subnet edge).
resource "aws_network_acl" "data" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.data[*].id
  tags       = merge(var.tags, { Name = "${var.name_prefix}-data-nacl" })
}

resource "aws_network_acl_rule" "data_ingress_vpc" {
  network_acl_id = aws_network_acl.data.id
  rule_number    = 100
  egress         = false
  protocol       = "-1"
  rule_action    = "allow"
  cidr_block     = var.vpc_cidr
}

resource "aws_network_acl_rule" "data_egress_vpc" {
  network_acl_id = aws_network_acl.data.id
  rule_number    = 100
  egress         = true
  protocol       = "-1"
  rule_action    = "allow"
  cidr_block     = var.vpc_cidr
}
