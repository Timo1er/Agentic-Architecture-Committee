# FinOps Principles & Multi-Cloud Costing Reference (FinOps Agent)

Standards evaluated by the FinOps Agent:

## 1. Capacity Planning & Right-Sizing
- **Workload Categorization**:
  - Variable / Bursty -> Serverless (AWS Lambda, GCP Cloud Run, Azure Container Apps, AliCloud Function Compute).
  - Steady State -> Reserved Instances (RIs) / Savings Plans / Committed Use Discounts (CUDs) - 1 to 3-year commitment (30-60% savings).
  - Batch / Fault-tolerant -> Spot / Preemptible instances (70-90% savings).

## 2. Multi-Cloud Egress & Data Transfer Optimization
- Cross-region and cross-cloud egress fees represent high hidden costs.
- Use CDN edge caching (CloudFront, Cloud CDN, Azure Front Door) to minimize origin egress.
- Keep high-volume database replica and analytical consumers within the same availability zone or region.

## 3. Storage Lifecycle Management
- Automated tiering: S3 Standard -> S3 Infrequent Access -> Glacier Instant Retrieval -> Glacier Deep Archive.
- Equivalent tiers on GCP (Standard, Nearline, Coldline, Archive), Azure (Hot, Cool, Cold, Archive), AliCloud OSS, and OVH Cloud Archive.
