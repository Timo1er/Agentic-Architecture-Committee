import json
import logging
import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from backend.core.drawio_generator import DrawIOGenerator

logger = logging.getLogger("arb.builder_agents")

# Default service mappings across clouds
CLOUD_SERVICE_CATALOG = {
    "AWS": {
        "edge": "Amazon CloudFront & AWS WAFv2",
        "ingress": "Application Load Balancer (ALB) / API Gateway",
        "compute": "Amazon ECS (Fargate) / EKS Managed Cluster",
        "compute_serverless": "AWS Lambda + EventBridge",
        "database_relational": "Amazon Aurora PostgreSQL (Multi-AZ Serverless v2)",
        "database_nosql": "Amazon DynamoDB (On-Demand Global Tables)",
        "cache": "Amazon ElastiCache for Redis (Cluster Mode)",
        "messaging": "Amazon SQS & SNS / Amazon Managed Streaming for Kafka (MSK)",
        "storage": "Amazon S3 (Standard + Glacier Instant Retrieval)",
        "security": "AWS KMS (CMEK) + Secrets Manager + IAM Roles",
        "observability": "Amazon CloudWatch & AWS X-Ray"
    },
    "GCP": {
        "edge": "Google Cloud Armor & Cloud CDN",
        "ingress": "Global External HTTPS Load Balancer / API Gateway",
        "compute": "Google Kubernetes Engine (GKE Autopilot) / Cloud Run",
        "compute_serverless": "Cloud Functions (2nd Gen)",
        "database_relational": "AlloyDB for PostgreSQL / Cloud SQL (High Availability)",
        "database_nosql": "Cloud Firestore / Bigtable",
        "cache": "Google Cloud Memorystore for Redis",
        "messaging": "Google Cloud Pub/Sub",
        "storage": "Google Cloud Storage (Dual-Region with CMEK)",
        "security": "Cloud KMS + Secret Manager + Workload Identity",
        "observability": "Google Cloud Operations Suite (Cloud Monitoring & Cloud Logging)"
    },
    "Azure": {
        "edge": "Azure Front Door & Web Application Firewall (WAF)",
        "ingress": "Azure Application Gateway (WAF v2)",
        "compute": "Azure Kubernetes Service (AKS) / Azure Container Apps",
        "compute_serverless": "Azure Functions (Premium Plan)",
        "database_relational": "Azure Database for PostgreSQL (Flexible Server HA)",
        "database_nosql": "Azure Cosmos DB (Multi-Region Writes)",
        "cache": "Azure Cache for Redis (Enterprise Tier)",
        "messaging": "Azure Service Bus (Premium) / Event Hubs",
        "storage": "Azure Blob Storage (Zone-Redundant Storage ZRS)",
        "security": "Azure Key Vault + Microsoft Entra ID Managed Identities",
        "observability": "Azure Monitor & Application Insights"
    },
    "AliCloud": {
        "edge": "Alibaba Cloud CDN & Anti-DDoS Pro / WAF 3.0",
        "ingress": "Server Load Balancer (SLB / ALB)",
        "compute": "Container Service for Kubernetes (ACK) / Serverless App Engine",
        "compute_serverless": "Function Compute (FC)",
        "database_relational": "ApsaraDB RDS for PostgreSQL (High Availability Edition)",
        "database_nosql": "ApsaraDB for Tablestore / MongoDB",
        "cache": "ApsaraDB for Redis (Cluster Edition)",
        "messaging": "Message Queue for Apache RocketMQ / MNS",
        "storage": "Object Storage Service (OSS - Cross-Region Replication)",
        "security": "Alibaba Cloud KMS + RAM (Resource Access Management)",
        "observability": "Application Real-Time Monitoring Service (ARMS) & CloudMonitor"
    },
    "OVH": {
        "edge": "OVHcloud Anti-DDoS & CDN Infrastructure",
        "ingress": "OVHcloud Managed Load Balancer",
        "compute": "OVHcloud Managed Kubernetes Service (K8s)",
        "compute_serverless": "OVHcloud AI Deploy / Worker Nodes",
        "database_relational": "OVHcloud Managed Databases for PostgreSQL (HA Triple-Node)",
        "database_nosql": "OVHcloud Managed Databases for MongoDB",
        "cache": "OVHcloud Managed Databases for Redis",
        "messaging": "OVHcloud Managed Databases for Apache Kafka",
        "storage": "OVHcloud High Performance Object Storage (S3 API - Sovereign EU)",
        "security": "OVHcloud KMS & IAM Zero Trust Policies",
        "observability": "OVHcloud Metrics & Managed Grafana / Prometheus"
    },
    "Multi-Cloud": {
        "edge": "Cloudflare Enterprise WAF & Global Anycast CDN",
        "ingress": "Envoy Gateway / Kubernetes Ingress Controller",
        "compute": "Multi-Cloud Kubernetes (EKS / GKE / AKS)",
        "compute_serverless": "Knative / Cloud Native Functions",
        "database_relational": "CockroachDB Dedicated / Cloud-Agnostic PostgreSQL HA",
        "database_nosql": "MongoDB Atlas / ScyllaDB",
        "cache": "Redis Enterprise Cloud (Multi-Cloud Active-Active)",
        "messaging": "Confluent Cloud Kafka / Apache Pulsar",
        "storage": "Multi-Cloud Object Storage (S3 + GCS + Azure Blob)",
        "security": "HashiCorp Vault + Multi-Cloud SPIFFE/SPIRE Identity",
        "observability": "Datadog / OpenTelemetry + Grafana Mimir"
    }
}

BUILD_PROPOSAL_SYSTEM_PROMPT = """You are an elite **Principal Cloud Solutions Architect** and Lead Reviewer for the Architecture Review Board (ARB).
Your task is to take customer requirements, system specifications, or an on-premise inventory (provided via text or parsed from Excel/Word/PDF) and engineer a comprehensive, production-grade target cloud architecture strictly tailored to the requested Cloud Provider ({cloud_provider}).

Requirements:
1. Target Cloud: Strictly use native, modern services for **{cloud_provider}**. (e.g. AWS: ALB, ECS Fargate, Aurora; GCP: Cloud Run, GKE, AlloyDB; Azure: Container Apps, AKS, Azure SQL; AliCloud: ACK, ApsaraDB; OVH: Managed K8s, Managed PostgreSQL).
2. Produce a **Detailed Architecture Components Table** (minimum 6-10 components covering Ingress, Compute, Database, Caching, Messaging, Storage, Security, Observability).
3. Produce a clean **Mermaid.js diagram** with subgraphs representing network tiers/subnets.
4. Synthesize a complete **Technical Architecture Document (TAD)** in professional Markdown format.

You MUST respond in valid JSON with this exact schema:
{{
  "title": "Clean, descriptive title for the architecture",
  "target_cloud": "{cloud_provider}",
  "architecture_style": "Event-Driven Microservices / Modulith / Lakehouse / etc.",
  "executive_summary": "2-3 paragraphs summarizing the proposed architecture, business value, and modernization rationale.",
  "total_estimated_monthly_usd": 1850.0,
  "cost_drivers_summary": "Primary cost drivers: Managed Database, Compute Nodes, Cross-AZ data transfer.",
  "components": [
    {{
      "name": "Component Name",
      "tier": "Edge & Ingress" | "Application / Compute" | "Database & State" | "Messaging & Async" | "Security & Observability",
      "cloud_service": "Exact native {cloud_provider} service name",
      "sizing": "vCPU, RAM, auto-scaling parameters, storage capacity",
      "purpose": "Precise responsibility and role in architecture",
      "ha_resilience": "Multi-AZ, failover time, backup strategy, SLA",
      "security_networking": "VPC subnet, KMS encryption, firewall/WAF rule, IAM role",
      "monthly_cost_usd": 150.0
    }}
  ],
  "diagram_mermaid": "graph TD\\n    subgraph Ingress[\"Public Ingress Zone\"]\\n        ...\\n    end",
  "full_tad_markdown": "# Technical Architecture Document (TAD)..."
}}
"""

class CloudArchitectureBuilder:
    """Builds comprehensive cloud architecture proposals from text or extracted document contents."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    @classmethod
    def get_smart_fallback(
        cls,
        title: str,
        cloud_provider: str,
        input_text: str,
        workload_type: str = "Microservices & Web Apps",
        high_availability: str = "Multi-AZ",
        compliance: str = "Standard",
        budget_tier: str = "Mid-Market"
    ) -> Dict[str, Any]:
        """Generate high-quality, realistic cloud architecture proposal for the specified cloud provider."""
        cp = cloud_provider if cloud_provider in CLOUD_SERVICE_CATALOG else "AWS"
        cat = CLOUD_SERVICE_CATALOG[cp]

        # Determine cost multiplier based on budget tier
        cost_mult = 0.5 if "startup" in budget_tier.lower() else (2.2 if "enterprise" in budget_tier.lower() else 1.0)

        components = [
            {
                "name": "Edge Ingress & WAF Gateway",
                "tier": "Edge & Ingress",
                "cloud_service": cat["edge"],
                "sizing": "Anycast Global Edge, Managed OWASP Top 10 Ruleset, Rate Limiting (5,000 req/min)",
                "purpose": "Terminates public TLS 1.3, mitigates DDoS/bot attacks, applies geo-blocking and edge caching.",
                "ha_resilience": "Global point-of-presence redundancy, 99.99% availability SLA, automatic multi-POP failover.",
                "security_networking": "Public edge DMZ, customer-managed TLS certificates, AWS/Cloud WAF inspected egress.",
                "monthly_cost_usd": round(140.0 * cost_mult, 2)
            },
            {
                "name": "Load Balancing & Traffic Router",
                "tier": "Edge & Ingress",
                "cloud_service": cat["ingress"],
                "sizing": "Layer-7 Path/Header Routing, Health Checks (5s interval), Multi-AZ listeners",
                "purpose": "Routes incoming REST/GraphQL traffic across microservice pods and private container tasks.",
                "ha_resilience": "Deploys across 3 availability zones with zero-downtime rolling health-check drains.",
                "security_networking": "Public-facing subnet, security groups restricting inbound to CloudFront/CDN IPs only.",
                "monthly_cost_usd": round(75.0 * cost_mult, 2)
            },
            {
                "name": "Core Application & API Microservices",
                "tier": "Application / Compute",
                "cloud_service": cat["compute"],
                "sizing": "8x vCPU / 32GB RAM baseline cluster, Horizontal Pod Autoscaler (HPA) 4 to 20 nodes at 70% CPU",
                "purpose": "Hosts containerized domain microservices (Accounts, Catalog, Orders, Notification workers).",
                "ha_resilience": f"{high_availability} pod anti-affinity, multi-zone distributed worker placement.",
                "security_networking": "Strictly private VPC subnets with no public IPs; outbound egress via NAT Gateway.",
                "monthly_cost_usd": round(580.0 * cost_mult, 2)
            },
            {
                "name": "High-Performance Primary Database",
                "tier": "Database & State",
                "cloud_service": cat["database_relational"],
                "sizing": "4 vCPU / 16GB RAM primary instance + 1 Auto-Scaling Read Replica, 250GB NVMe SSD (Encrypted)",
                "purpose": "Primary ACID transactional relational datastore for relational domain entities and ledger.",
                "ha_resilience": "Synchronous multi-AZ replication, automated failover under 30 seconds, 35-day point-in-time recovery.",
                "security_networking": "Isolated Database Subnet, no internet gateway routing, encrypted at rest via CMEK KMS.",
                "monthly_cost_usd": round(450.0 * cost_mult, 2)
            },
            {
                "name": "Distributed In-Memory Cache",
                "tier": "Database & State",
                "cloud_service": cat["cache"],
                "sizing": "2-node Cluster (cache.m6g.large / 6.3GB RAM each), automatic in-memory sharding",
                "purpose": "Sub-millisecond query caching, session store, distributed rate limiter tokens, and pub/sub cache.",
                "ha_resilience": "Multi-AZ automatic failover with active primary and hot standby replica.",
                "security_networking": "Private data subnet, in-transit encryption (TLS), AUTH password token rotation.",
                "monthly_cost_usd": round(165.0 * cost_mult, 2)
            },
            {
                "name": "Asynchronous Message Queue & Event Stream",
                "tier": "Messaging & Async",
                "cloud_service": cat["messaging"],
                "sizing": "Managed Topic/Queue cluster, partitioned throughput up to 10k msgs/sec, Dead Letter Queue (DLQ)",
                "purpose": "Decouples microservice domain boundaries, enables Outbox Pattern and guaranteed at-least-once delivery.",
                "ha_resilience": "Triple-zone partition replication, 14-day message retention safety buffer.",
                "security_networking": "Private VPC endpoint / PrivateLink, IAM fine-grained produce/consume access policies.",
                "monthly_cost_usd": round(120.0 * cost_mult, 2)
            },
            {
                "name": "Durable Object Storage & Backup Vault",
                "tier": "Database & State",
                "cloud_service": cat["storage"],
                "sizing": "5TB Hot Tier + Automated 30-day lifecycle transition to Cold Archive Tier",
                "purpose": "Stores unstructured digital assets, customer documents, static payloads, and automated database backups.",
                "ha_resilience": "99.999999999% (11 9s) durability, multi-region zone replication.",
                "security_networking": "Public access completely blocked, server-side KMS encryption enforced, Object Lock enabled.",
                "monthly_cost_usd": round(110.0 * cost_mult, 2)
            },
            {
                "name": "Zero-Trust Identity, Secrets & Key Vault",
                "tier": "Security & Observability",
                "cloud_service": cat["security"],
                "sizing": "Customer-Managed Keys (CMEK) with automatic annual rotation, 30 secret leases",
                "purpose": "Centralized cryptography keys, API token storage, and fine-grained least-privilege IAM control.",
                "ha_resilience": "Cloud native managed high-availability key store backed by FIPS 140-2 Level 3 HSMs.",
                "security_networking": "Private VPC endpoint, strict resource-based policies, audit trail logged to CloudTrail/Audit.",
                "monthly_cost_usd": round(60.0 * cost_mult, 2)
            },
            {
                "name": "Centralized Telemetry & Observability",
                "tier": "Security & Observability",
                "cloud_service": cat["observability"],
                "sizing": "50GB ingested logs/mo, 100 custom metrics, distributed tracing sampling (5%)",
                "purpose": "Unified log ingestion, APM distributed request tracing, latency SLO dashboards, and automated alert paging.",
                "ha_resilience": "SaaS / Cloud native high-availability monitoring pipeline.",
                "security_networking": "Encrypted telemetry streams, role-based access control for compliance audit logs.",
                "monthly_cost_usd": round(120.0 * cost_mult, 2)
            }
        ]

        total_cost = sum(c["monthly_cost_usd"] for c in components)

        # Mermaid Diagram
        mermaid_code = f"""graph TD
    subgraph Edge["1. Edge & Ingress Zone"]
        CDN["{cat['edge']}"]
        LB["{cat['ingress']}"]
        CDN -->|"HTTPS (TLS 1.3)"| LB
    end

    subgraph AppTier["2. Private Application Subnet"]
        APP["{cat['compute']}"]
        WORKER["Async Background Workers"]
        LB -->|"Internal Load Balancing"| APP
        APP -->|"Task Offload"| WORKER
    end

    subgraph DataTier["3. Secure Data & Persistence Subnet"]
        CACHE["{cat['cache']}"]
        DB[(" {cat['database_relational']} ")]
        STORAGE[(" {cat['storage']} ")]
        APP -->|"Fast Reads & Sessions"| CACHE
        APP -->|"ACID Writes & Queries"| DB
        APP -->|"Media & Assets"| STORAGE
    end

    subgraph MessagingTier["4. Event Streaming & Decoupling"]
        QUEUE["{cat['messaging']}"]
        APP -->|"Outbox Events"| QUEUE
        QUEUE -->|"Reliable Processing"| WORKER
    end

    subgraph Governance["5. Zero-Trust & Observability"]
        KMS["{cat['security']}"]
        OBS["{cat['observability']}"]
        DB -.->|"CMEK Key"| KMS
        APP -.->|"Metrics & Traces"| OBS
    end

    classDef edgeStyle fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#fff;
    classDef compStyle fill:#1e293b,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef dataStyle fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#fff;
    class CDN,LB edgeStyle;
    class APP,WORKER compStyle;
    class DB,CACHE,STORAGE dataStyle;
"""

        # Full Technical Architecture Document (TAD)
        tad_markdown = f"""# Technical Architecture Document (TAD)
## {title}

- **Target Cloud Provider:** `{cp}`
- **Architecture Pattern:** `{workload_type} (Cloud-Native {high_availability})`
- **Estimated Monthly Run-Rate:** `${total_cost:,.2f} USD`
- **Compliance Baseline:** `{compliance} & CIS Benchmarks`
- **Generated by:** Architecture Review Board (ARB) Multi-Agent Cloud Platform

---

### 1. Executive Summary
This Technical Architecture Document details the comprehensive production cloud topology for **{title}** hosted on **{cp}**. Designed to transition workloads into an elastic, resilient, and enterprise-grade posture, the architecture establishes strict network isolation, automated scaling, multi-AZ high availability, and defense-in-depth zero-trust security controls.

The design decouples synchronous user requests from background asynchronous workflows, mitigating cascading failure modes while optimizing monthly cloud spend through reserved capacity planning and managed serverless services.

---

### 2. Architecture Principles & Design Patterns
1. **Zero-Trust Network Isolation:** Public entry points are strictly constrained to the Edge and Ingress zone. Compute, databases, and message brokers reside in non-routable private subnets.
2. **Elastic Scalability & Auto-Recovery:** Horizontal autoscaling triggers across compute pods based on CPU and memory thresholds, with automated health checks that isolate degraded instances without manual intervention.
3. **Data Integrity & Asynchronous Decoupling:** Employs the Transactional Outbox Pattern combined with **{cat['messaging']}** to guarantee at-least-once delivery for state changes across domain boundaries.
4. **Data Sovereignty & Compliance:** All stateful storage is encrypted at rest using Customer-Managed Keys (CMEK) via **{cat['security']}**, fulfilling `{compliance}` requirements.

---

### 3. Detailed Architecture Components Matrix

| Component Name | Tier / Layer | Cloud Native Service ({cp}) | Sizing & Configuration | Key Responsibilities | High Availability | Security & Network | Est. Cost (USD/mo) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

        for c in components:
            tad_markdown += f"| **{c['name']}** | {c['tier']} | `{c['cloud_service']}` | {c['sizing']} | {c['purpose']} | {c['ha_resilience']} | {c['security_networking']} | ${c['monthly_cost_usd']:,.2f} |\n"

        tad_markdown += f"""
| **TOTAL ESTIMATED SPEND** | **ALL TIERS** | **{cp} Infrastructure** | **Comprehensive Full Stack** | **End-to-End Enterprise Solution** | **Multi-AZ HA** | **Zero-Trust Guardrails** | **${total_cost:,.2f}/mo** |

---

### 4. High Availability & Disaster Recovery (HA/DR)
- **Target Recovery Time Objective (RTO):** `< 15 minutes` via automated infrastructure-as-code re-provisioning and managed database failover.
- **Target Recovery Point Objective (RPO):** `< 1 minute` via continuous write-ahead log shipping and synchronous multi-AZ storage replication.
- **Cross-Region Strategy:** Periodic cross-region snapshots of the primary relational database and bucket replication for disaster recovery.

---

### 5. Security & Compliance Blueprint
- **Identity & Access Management:** No long-lived cloud credentials; all workloads authenticate using workload identity federation / IAM roles.
- **Network Boundaries:** Ingress WAF filters OWASP Top 10 vulnerabilities; egress filtered via NAT Gateway with whitelisted destinations.
- **Cryptography:** TLS 1.3 enforced on all external and inter-service communication; AES-256 GCM encryption at rest with CMEK keys.

---

### 6. Phased Implementation & Migration Roadmap
1. **Phase 1: Foundation & Network Setup (Weeks 1-2):** Deploy {cp} VPC, subnets, transit routing, KMS keys, and CI/CD deployment pipelines.
2. **Phase 2: Database & Data Migration (Weeks 3-4):** Provision {cat['database_relational']}, execute initial schema migration, configure continuous replication.
3. **Phase 3: Compute & Microservice Deployment (Weeks 5-6):** Deploy containerized workloads onto {cat['compute']}, configure HPA, ingress routing, and observability dashboards.
4. **Phase 4: Cutover & Validation (Week 7):** Execute load tests, game day failure drills, DNS switchover, and decommission legacy infrastructure.
"""

        # Generate standard Draw.io XML
        drawio_xml = DrawIOGenerator.generate_xml(
            title=title,
            cloud_provider=cp,
            components=components
        )

        return {
            "title": title,
            "target_cloud": cp,
            "architecture_style": f"{workload_type} (Cloud-Native)",
            "executive_summary": f"Comprehensive cloud-native architecture for {title} engineered on {cp}. Adheres to Well-Architected Framework guidelines and zero-trust security baselines.",
            "total_estimated_monthly_usd": total_cost,
            "cost_drivers_summary": f"Compute ({cat['compute']}) and Managed Relational Database ({cat['database_relational']}) constitute ~60% of total spend.",
            "components": components,
            "diagram_mermaid": mermaid_code,
            "diagram_drawio_xml": drawio_xml,
            "full_tad_markdown": tad_markdown
        }

    async def propose_architecture(
        self,
        title: str,
        cloud_provider: str,
        input_text: str,
        workload_type: str = "Microservices & Web Apps",
        high_availability: str = "Multi-AZ",
        compliance: str = "Standard",
        budget_tier: str = "Mid-Market"
    ) -> Dict[str, Any]:
        """Propose cloud architecture using LLM with resilient smart fallback."""
        cp = cloud_provider.upper() if cloud_provider.upper() in CLOUD_SERVICE_CATALOG else cloud_provider

        # Check if LLM is mock or not available
        llm_type = getattr(self.llm, "_llm_type", "")
        if "mock" in llm_type.lower():
            logger.info(f"Using smart architecture synthesis fallback for {cp} ({title}).")
            return self.get_smart_fallback(
                title=title,
                cloud_provider=cp,
                input_text=input_text,
                workload_type=workload_type,
                high_availability=high_availability,
                compliance=compliance,
                budget_tier=budget_tier
            )

        prompt_system = BUILD_PROPOSAL_SYSTEM_PROMPT.format(cloud_provider=cp)
        prompt_user = f"""Please design a production-grade cloud architecture for the following target system:

System Title: {title}
Target Cloud Provider: {cp}
Workload Archetype: {workload_type}
High Availability SLA: {high_availability}
Regulatory / Compliance Focus: {compliance}
Budget / Scale Tier: {budget_tier}

System Requirements & Input Specification:
{input_text[:8000]}

Generate the complete architecture proposal with a detailed components table, Mermaid.js diagram, and comprehensive Technical Architecture Document.
"""

        messages = [
            SystemMessage(content=prompt_system),
            HumanMessage(content=prompt_user)
        ]

        try:
            if hasattr(self.llm, "ainvoke"):
                resp = await self.llm.ainvoke(messages)
            else:
                resp = self.llm.invoke(messages)

            raw_text = resp.content if hasattr(resp, "content") else str(resp)
            if isinstance(raw_text, list):
                raw_text = " ".join([str(item.get("text", item) if isinstance(item, dict) else item) for item in raw_text])

            # Extract JSON block
            json_text = raw_text.strip()
            fence_m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', json_text)
            if fence_m:
                json_text = fence_m.group(1).strip()
            else:
                start = json_text.find('{')
                end = json_text.rfind('}')
                if start != -1 and end > start:
                    json_text = json_text[start:end+1]

            parsed = json.loads(json_text, strict=False)

            # Ensure Draw.io XML is always generated and valid
            if "components" in parsed and isinstance(parsed["components"], list):
                parsed["diagram_drawio_xml"] = DrawIOGenerator.generate_xml(
                    title=parsed.get("title", title),
                    cloud_provider=cp,
                    components=parsed["components"]
                )
            else:
                fallback = self.get_smart_fallback(title, cp, input_text, workload_type, high_availability, compliance, budget_tier)
                parsed["components"] = fallback["components"]
                parsed["diagram_drawio_xml"] = fallback["diagram_drawio_xml"]

            if not parsed.get("diagram_mermaid"):
                fallback = self.get_smart_fallback(title, cp, input_text, workload_type, high_availability, compliance, budget_tier)
                parsed["diagram_mermaid"] = fallback["diagram_mermaid"]

            if not parsed.get("full_tad_markdown"):
                fallback = self.get_smart_fallback(title, cp, input_text, workload_type, high_availability, compliance, budget_tier)
                parsed["full_tad_markdown"] = fallback["full_tad_markdown"]

            return parsed
        except Exception as e:
            logger.warning(f"Live LLM generation for {cp} encountered error: {e}. Utilizing smart fallback.")
            return self.get_smart_fallback(
                title=title,
                cloud_provider=cp,
                input_text=input_text,
                workload_type=workload_type,
                high_availability=high_availability,
                compliance=compliance,
                budget_tier=budget_tier
            )
