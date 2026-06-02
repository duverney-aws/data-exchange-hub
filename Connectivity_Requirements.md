# Connectivity Requirements for AWS Glue Connectors

## You're Absolutely Correct!

Yes, for AWS Glue to connect to on-premise databases (Oracle, SQL Server, SAP, etc.), you need **network connectivity** from AWS to the CMO's on-premise environment.

---

## Connectivity Options (3 Choices)

### Option 1: AWS Direct Connect (Recommended for Production)
**What it is:** Dedicated private network connection from CMO data center to AWS

```
┌─────────────────────────────────────────────────────────────────┐
│  CMO On-Premise Data Center                                     │
│                                                                  │
│  ┌──────────────┐                                               │
│  │  Oracle DB   │                                               │
│  │  SQL Server  │                                               │
│  │  SAP HANA    │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐         ┌─────────────────┐                  │
│  │  Router      │────────▶│ Direct Connect  │                  │
│  │              │         │ Location        │                  │
│  └──────────────┘         └────────┬────────┘                  │
└────────────────────────────────────┼─────────────────────────────┘
                                     │
                                     │ Dedicated 1Gbps or 10Gbps
                                     │ Private Connection
                                     │
┌────────────────────────────────────┼─────────────────────────────┐
│  AWS Account (Merck)               │                             │
│                                    ▼                             │
│                          ┌─────────────────┐                     │
│                          │ Virtual Private │                     │
│                          │ Gateway (VGW)   │                     │
│                          └────────┬────────┘                     │
│                                   │                              │
│                                   ▼                              │
│                          ┌─────────────────┐                     │
│                          │      VPC        │                     │
│                          │  ┌───────────┐  │                     │
│                          │  │ AWS Glue  │  │                     │
│                          │  │ Connector │  │                     │
│                          │  └───────────┘  │                     │
│                          └─────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Dedicated bandwidth (predictable performance)
- ✅ Low latency (1-10ms)
- ✅ Secure (private connection, not over internet)
- ✅ Consistent throughput for large data transfers

**Cons:**
- ❌ Takes 2-4 weeks to provision
- ❌ Higher cost ($300-$1000/month + data transfer)
- ❌ Requires physical installation at Direct Connect location

**Best for:** Production workloads, large data volumes (>100GB), multiple CMOs

---

### Option 2: Site-to-Site VPN (Faster Setup)
**What it is:** Encrypted VPN tunnel over the internet

```
┌─────────────────────────────────────────────────────────────────┐
│  CMO On-Premise Data Center                                     │
│                                                                  │
│  ┌──────────────┐                                               │
│  │  Oracle DB   │                                               │
│  │  SQL Server  │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │  VPN Device  │                                               │
│  │  (Firewall)  │                                               │
│  └──────┬───────┘                                               │
└─────────┼───────────────────────────────────────────────────────┘
          │
          │ IPsec VPN Tunnel
          │ Over Internet (Encrypted)
          │
┌─────────┼───────────────────────────────────────────────────────┐
│  AWS    │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ Virtual      │                                               │
│  │ Private      │                                               │
│  │ Gateway      │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │     VPC      │                                               │
│  │ ┌──────────┐ │                                               │
│  │ │AWS Glue  │ │                                               │
│  │ └──────────┘ │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Quick setup (1-2 days)
- ✅ Lower cost (~$36/month + data transfer)
- ✅ No physical installation required
- ✅ Good for pilot/POC

**Cons:**
- ❌ Performance depends on internet connection
- ❌ Variable latency (20-100ms)
- ❌ Bandwidth limited by internet connection
- ❌ Not ideal for large data transfers

**Best for:** Pilot projects, small data volumes (<10GB), quick setup needed

---

### Option 3: AWS Client VPN (For Testing Only)
**What it is:** Individual user VPN connection

**Pros:**
- ✅ Very quick setup (hours)
- ✅ No infrastructure changes needed

**Cons:**
- ❌ Not suitable for production
- ❌ Requires user authentication
- ❌ Limited bandwidth

**Best for:** Testing connectivity during onboarding only

---

## What Gets Configured During Pattern Selection

When a CMO selects **Pattern 1 (Glue Connectors)** in the portal, they provide:

### Step 1: Connectivity Details
```json
{
  "connectivity_type": "site_to_site_vpn",  // or "direct_connect"
  "connectivity_status": "existing",         // or "needs_setup"
  
  "network_details": {
    "cmo_cidr_range": "10.50.0.0/16",
    "database_subnet": "10.50.10.0/24",
    "vpn_endpoint_ip": "203.0.113.45",      // CMO's public IP
    "bgp_asn": 65000                         // For Direct Connect
  }
}
```

### Step 2: Database Connection Details
```json
{
  "database_type": "oracle",
  "host": "10.50.10.25",                    // Private IP (reachable via VPN/DX)
  "port": 1521,
  "database_name": "PRODDB",
  "authentication": {
    "method": "username_password",          // Stored in Secrets Manager
    "secret_arn": "arn:aws:secretsmanager:us-east-1:123456789:secret:cmo-alpha-db"
  },
  "ssl_enabled": true,
  "ssl_certificate_s3": "s3://certs/cmo-alpha-oracle.pem"
}
```

### Step 3: Glue Connection Configuration
```json
{
  "glue_connection_name": "cmo-alpha-oracle-prod",
  "connection_type": "JDBC",
  "jdbc_url": "jdbc:oracle:thin:@10.50.10.25:1521/PRODDB",
  "vpc_id": "vpc-0abc123",
  "subnet_id": "subnet-0def456",
  "security_group_id": "sg-0ghi789",
  "availability_zone": "us-east-1a"
}
```

---

## Setup Process (Step-by-Step)

### For CMOs with Existing Connectivity (Fast Track)
```
1. CMO selects Pattern 1 in portal
2. CMO indicates "We already have Direct Connect/VPN to AWS"
3. CMO provides:
   - VPC ID where connectivity exists
   - Subnet IDs
   - Security group allowing Glue access
   - Database connection details
4. Lambda creates Glue Connection
5. Lambda tests connectivity
6. If successful → Pipeline deployed
7. If failed → Error message with troubleshooting steps

Timeline: 30 minutes
```

### For CMOs Without Connectivity (Needs Setup)
```
1. CMO selects Pattern 1 in portal
2. CMO indicates "We need to setup connectivity"
3. Portal shows two options:
   a) Site-to-Site VPN (1-2 days setup)
   b) Direct Connect (2-4 weeks setup)
4. CMO selects option
5. Portal generates setup guide with:
   - VPN configuration file (for option a)
   - Direct Connect LOA-CFA (for option b)
   - Firewall rules needed
   - IP whitelisting requirements
6. CMO IT team implements connectivity
7. CMO returns to portal, clicks "Test Connectivity"
8. If successful → Continue with database details
9. Pipeline deployed

Timeline: 
- VPN: 1-3 days
- Direct Connect: 2-4 weeks
```

---

## Security Considerations

### Firewall Rules (CMO Side)
CMO must allow outbound connections from database to AWS:

```
Source: Database Server (10.50.10.25)
Destination: AWS Glue VPC CIDR (10.0.0.0/16)
Ports: 
  - Oracle: 1521
  - SQL Server: 1433
  - PostgreSQL: 5432
  - MySQL: 3306
  - SAP HANA: 30015
Protocol: TCP
Direction: Outbound
```

### Security Groups (AWS Side)
AWS Glue needs security group allowing:

```
Inbound: None (Glue initiates connection)
Outbound: 
  - Destination: CMO database IP (10.50.10.25)
  - Port: Database port (e.g., 1521 for Oracle)
  - Protocol: TCP
```

### Secrets Management
Database credentials stored in AWS Secrets Manager:

```json
{
  "username": "glue_readonly_user",
  "password": "encrypted_password",
  "rotation_enabled": true,
  "rotation_days": 90
}
```

---

## Pattern Selection Decision Tree

```
CMO has on-premise database (Oracle, SQL Server, SAP)?
│
├─ YES → Does CMO already have AWS connectivity?
│         │
│         ├─ YES → Use Pattern 1 (Glue Connectors)
│         │        Setup time: 30 minutes
│         │
│         └─ NO → Two options:
│                  │
│                  ├─ Quick pilot needed?
│                  │   → Setup Site-to-Site VPN
│                  │      Setup time: 1-3 days
│                  │      Use Pattern 1
│                  │
│                  └─ Production workload?
│                      → Setup Direct Connect
│                         Setup time: 2-4 weeks
│                         Use Pattern 1
│
└─ NO → CMO database is cloud-based or CMO prefers file transfer?
         │
         ├─ Cloud database → Use Pattern 1 (Glue Connectors)
         │                   No VPN needed (internet accessible)
         │
         └─ Prefers file transfer → Use Pattern 2 (Transfer Family)
                                     No database connectivity needed
```

---

## Connectivity Testing (Automated)

When CMO submits connection details, Lambda automatically tests:

```python
def test_connectivity(connection_details):
    """
    Automated connectivity test during onboarding
    """
    tests = [
        {
            "name": "Network Reachability",
            "test": "ping database host via VPN/DX",
            "expected": "Host reachable"
        },
        {
            "name": "Port Accessibility",
            "test": "telnet to database port",
            "expected": "Port open"
        },
        {
            "name": "Database Authentication",
            "test": "Connect with provided credentials",
            "expected": "Authentication successful"
        },
        {
            "name": "Query Execution",
            "test": "SELECT 1 FROM DUAL",
            "expected": "Query returns result"
        },
        {
            "name": "Schema Access",
            "test": "List tables in specified schema",
            "expected": "Tables visible"
        }
    ]
    
    results = []
    for test in tests:
        result = run_test(test)
        results.append(result)
        if not result.passed:
            return {
                "status": "failed",
                "failed_test": test.name,
                "error": result.error,
                "remediation": get_remediation_steps(test.name)
            }
    
    return {
        "status": "success",
        "message": "All connectivity tests passed"
    }
```

---

## Cost Comparison

| Connectivity Option | Setup Cost | Monthly Cost | Data Transfer Cost | Best For |
|---------------------|------------|--------------|-------------------|----------|
| **Direct Connect (1Gbps)** | $0 | $300 | $0.02/GB | Production, >100GB/month |
| **Direct Connect (10Gbps)** | $0 | $2,250 | $0.02/GB | High volume, >1TB/month |
| **Site-to-Site VPN** | $0 | $36 | $0.09/GB | Pilot, <10GB/month |
| **No Connectivity (Pattern 2)** | $0 | $0 | $0.09/GB (S3 upload) | File-based transfer |

**Recommendation:** 
- Start with Site-to-Site VPN for pilot (2 CMOs)
- Upgrade to Direct Connect when scaling to 10+ CMOs

---

## Summary

**Your understanding is correct:**

1. ✅ On-premise databases need network connectivity (VPN or Direct Connect)
2. ✅ Connectivity details are captured during pattern selection
3. ✅ Portal guides CMO through setup if connectivity doesn't exist
4. ✅ Automated testing validates connectivity before pipeline deployment

**Key Insight:** 
- Pattern 1 (Glue Connectors) requires connectivity setup
- Pattern 2 (Transfer Family) does NOT require connectivity (CMO uploads files via SFTP)
- This is why Pattern 2 is the "universal fallback" - works for ANY CMO regardless of network setup

**Recommendation for Presentation:**
Emphasize that Pattern 2 (Transfer Family) can be used immediately while Direct Connect is being provisioned for Pattern 1. This allows CMOs to start sharing data on Day 1 via file transfer, then migrate to direct database connection later.
