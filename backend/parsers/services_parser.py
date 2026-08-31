import re
from typing import Dict, Any, List

class ServicesParser:
    """Parses plain-text cloud service lists, mapping them to providers and workload categories."""

    CLOUD_KEYWORDS = {
        "AWS": ["aws", "s3", "ec2", "rds", "lambda", "ecs", "eks", "dynamodb", "sqs", "sns", "kinesis", "cloudfront", "alb", "nlb", "api gateway", "fargate", "aurora", "bedrock", "msk"],
        "GCP": ["gcp", "google", "cloud storage", "gcs", "compute engine", "gke", "cloud run", "cloud functions", "cloud sql", "bigquery", "firestore", "pubsub", "pub/sub", "alloydb", "cloud spanner"],
        "Azure": ["azure", "blob storage", "aks", "container apps", "azure sql", "cosmos db", "service bus", "event hubs", "app service", "azure functions", "synapse"],
        "AliCloud": ["alicloud", "alibaba", "oss", "ecs", "ack", "apsaradb", "tablestore", "function compute", "slb", "rocketmq", "mns"],
        "OVH": ["ovh", "ovhcloud", "public cloud", "managed kubernetes", "vps", "dedicated server", "high grade", "hosted private cloud", "nutanix", "managed postgresql", "managed redis"]
    }

    CATEGORY_KEYWORDS = {
        "Compute": ["ec2", "vm", "compute engine", "ecs", "eks", "gke", "aks", "ack", "cloud run", "fargate", "container", "lambda", "cloud functions", "function compute", "vps", "server"],
        "Database": ["rds", "cloud sql", "aurora", "alloydb", "azure sql", "apsaradb", "postgres", "postgresql", "mysql", "mongodb", "dynamodb", "firestore", "cosmos db", "tablestore", "spanner"],
        "Storage": ["s3", "gcs", "cloud storage", "blob storage", "oss", "object storage", "ebs", "filestore", "persistent disk"],
        "Messaging / Streaming": ["kafka", "sqs", "sns", "pubsub", "pub/sub", "event hubs", "service bus", "rocketmq", "mns", "eventbridge", "kinesis", "rabbitmq", "nats"],
        "Networking & Security": ["alb", "nlb", "load balancer", "api gateway", "waf", "shield", "cloud armor", "cloudfront", "cdn", "front door", "vpc", "vpn", "direct connect", "interconnect", "slb"]
    }

    @classmethod
    def parse_text(cls, text: str) -> Dict[str, Any]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        detected_clouds = set()
        categorized_services = {cat: [] for cat in cls.CATEGORY_KEYWORDS}
        raw_services = []

        for line in lines:
            # Strip bullet points
            cleaned = re.sub(r'^[\*\-\d\.\>\s]+', '', line).strip()
            if not cleaned:
                continue
            raw_services.append(cleaned)
            lower_line = cleaned.lower()

            # Detect cloud provider
            for cloud, keywords in cls.CLOUD_KEYWORDS.items():
                if any(kw in lower_line for kw in keywords):
                    detected_clouds.add(cloud)

            # Categorize service
            matched_category = False
            for cat, keywords in cls.CATEGORY_KEYWORDS.items():
                if any(kw in lower_line for kw in keywords):
                    categorized_services[cat].append(cleaned)
                    matched_category = True
                    break
            
            if not matched_category:
                categorized_services.setdefault("Other / Custom", []).append(cleaned)

        return {
            "type": "services_list",
            "detected_clouds": list(detected_clouds) or ["Multi-Cloud / Generic"],
            "total_items": len(raw_services),
            "services_by_category": {k: v for k, v in categorized_services.items() if v},
            "raw_services": raw_services
        }
