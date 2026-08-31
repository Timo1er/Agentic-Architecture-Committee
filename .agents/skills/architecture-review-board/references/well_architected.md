# Well-Architected Framework: Multi-Cloud Review Reference

This reference outlines architectural standards used by the ARB Lead Architect and Validator agents across AWS, GCP, Azure, AliCloud, and OVH.

## 1. Modularity & Architecture Styles
- **Modular Monolith (Modulith)**: Recommended for early-to-mid stage domains, strict internal boundaries, in-memory event buses, single deployment artifact.
- **Microservices**: Recommended for independently scaling domains, multi-team autonomy, polyglot persistence. Requires distributed tracing, circuit breakers, and service mesh.
- **Event-Driven Architecture (EDA)**: Decoupled producers/consumers using Apache Kafka, AWS EventBridge/SNS/SQS, GCP Pub/Sub, Azure Event Grid, AliCloud MNS.
- **CQRS (Command Query Responsibility Segregation)**: Separate read/write models for high-throughput domains, paired with Event Sourcing or Read-Replica projections.

## 2. Cloud Provider Service Mappings
| Category | AWS | GCP | Azure | AliCloud | OVH |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Compute** | ECS / EKS / Lambda | Cloud Run / GKE / Cloud Functions | Container Apps / AKS | ACK / Function Compute | Managed Kubernetes / Public Cloud Instances |
| **Database (RDBMS)** | RDS / Aurora | Cloud SQL / AlloyDB | Azure SQL / Cosmos DB | ApsaraDB RDS | Managed PostgreSQL / MySQL |
| **Database (NoSQL)** | DynamoDB / DocumentDB | Firestore / Bigtable | Cosmos DB | Tablestore | Managed MongoDB / Redis |
| **Event Streaming** | Kafka (MSK) / SQS / SNS | Pub/Sub / Eventarc | Event Hubs / Service Bus | Message Queue / RocketMQ | Managed Kafka |
| **API Gateway** | API Gateway / ALB | Cloud Endpoints / Apigee | API Management | API Gateway | Kong / Traefik on OVH |
| **Object Storage** | S3 | Cloud Storage | Blob Storage | OSS | OVH Object Storage (S3-compatible) |
