---
name: architecture-review-board
description: >-
  Enterprise-grade multi-agent architecture review system evaluating workloads across AWS, GCP, Azure,
  AliCloud, and OVH. Orchestrates Lead Architect, SecOps & Compliance, FinOps, and Synthesis agents
  to produce structured Architecture Decision Records (ADRs), risk matrices, and continuous learning feedback.
---

# Architecture Review Board (ARB) Skill

The **Architecture Review Board (ARB)** skill equips Antigravity with autonomous multi-agent review capabilities for evaluating system designs, infrastructure-as-code (Terraform), plain-text cloud service inventories, and architecture diagrams (Mermaid.js / Draw.io).

## Core Capabilities

1. **Multi-Cloud Architecture Assessment**:
   - **AWS, GCP, Azure, AliCloud, OVH**: Deep domain knowledge of multi-region deployment models, managed services, interconnects, and vendor lock-in mitigation.
2. **Specialized Agent Evaluation Matrix**:
   - **Lead Architect Agent**: Analyzes architectural patterns (CQRS, Event-Driven, Microservices vs. Modulith, Saga Pattern, Outbox Pattern) and domain boundaries.
   - **SecOps & Compliance Agent**: Enforces OWASP Top 10, CIS Benchmarks, GDPR, zero-trust network boundaries, public ingress/egress audits, and encryption at rest/transit.
   - **FinOps Agent**: Evaluates monthly cost models, capacity reservations, autoscaling economics, tiering, and serverless vs. provisioned workloads.
   - **Synthesis & Validator Agent**: Aggregates all stream findings into a standardized Architecture Decision Record (ADR), builds risk matrices, and orchestrates human validation in the loop.
3. **Continuous Learning & Few-Shot Feedback**:
   - Vector database memory (pgvector / Qdrant) retrieves past human operator ratings, corrections, and enterprise guidelines to steer current recommendations.
