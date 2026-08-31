# Security Baselines & Compliance Reference (SecOps Agent)

Standards evaluated by the SecOps & Compliance Agent:

## 1. OWASP Top 10 & API Security
- **A01: Broken Access Control**: Verify strict IAM role separation, principle of least privilege, token revocation.
- **A02: Cryptographic Failures**: In-transit TLS 1.3 enforcement, customer-managed KMS keys (AWS KMS, GCP Cloud KMS, Azure Key Vault, AliCloud KMS, OVH KMS).
- **A03: Injection**: Parameterized SQL, ORM boundary checks, API schema validation.
- **A05: Security Misconfiguration**: Default credential removal, disabling unnecessary public endpoints, debug header suppression.

## 2. CIS Benchmarks & Network Flows
- **VPC / Subnet Isolation**: Public DMZ for load balancers only; Private isolated subnets for application workloads; Private database subnets with no direct IGW access.
- **Egress & Ingress Control**: Strict Security Group / Firewall definitions, NAT Gateways with static IP whitelisting, Web Application Firewalls (AWS WAF, Cloud Armor, Azure WAF).
- **Zero Trust Network Access (ZTNA)**: Mutual TLS (mTLS) for service-to-service communication.

## 3. GDPR & Data Sovereignty
- **Data Residency**: Strict regional isolation for EU user data (e.g. AWS eu-west-1, GCP europe-west1, Azure westeurope, OVH Gravelines/Roubaix/Strasbourg).
- **Pseudonymization & Encryption**: PII masking at rest, automated retention and deletion policies.
