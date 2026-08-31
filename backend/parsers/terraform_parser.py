import re
from typing import Dict, Any, List

class TerraformParser:
    """Parses Terraform HCL code (.tf) to extract cloud providers, resources, data sources, and variables."""

    @staticmethod
    def parse_hcl(hcl_content: str) -> Dict[str, Any]:
        resources = []
        providers = set()
        variables = []
        outputs = []

        # Extract providers
        provider_pattern = re.compile(r'provider\s+"([a-zA-Z0-9_\-]+)"\s*\{')
        for match in provider_pattern.finditer(hcl_content):
            providers.add(match.group(1))

        # Extract resources: resource "aws_s3_bucket" "my_bucket" {
        resource_pattern = re.compile(r'resource\s+"([a-zA-Z0-9_\-]+)"\s+"([a-zA-Z0-9_\-]+)"\s*\{([^}]*)\}', re.MULTILINE | re.DOTALL)
        for match in resource_pattern.finditer(hcl_content):
            res_type = match.group(1)
            res_name = match.group(2)
            res_body = match.group(3).strip()

            # Infer cloud provider from resource prefix
            inferred_provider = "unknown"
            if res_type.startswith("aws_"):
                inferred_provider = "AWS"
            elif res_type.startswith("google_") or res_type.startswith("gcp_"):
                inferred_provider = "GCP"
            elif res_type.startswith("azurerm_") or res_type.startswith("azure_"):
                inferred_provider = "Azure"
            elif res_type.startswith("alicloud_"):
                inferred_provider = "AliCloud"
            elif res_type.startswith("ovh_"):
                inferred_provider = "OVH"

            resources.append({
                "type": res_type,
                "name": res_name,
                "cloud": inferred_provider,
                "summary": f"{res_type}.{res_name}"
            })

        # Extract variables
        var_pattern = re.compile(r'variable\s+"([a-zA-Z0-9_\-]+)"\s*\{')
        for match in var_pattern.finditer(hcl_content):
            variables.append(match.group(1))

        return {
            "type": "terraform",
            "detected_providers": list(providers) or list(set(r["cloud"] for r in resources if r["cloud"] != "unknown")),
            "resource_count": len(resources),
            "resources": resources,
            "variables": variables,
            "raw_snippet": hcl_content[:500] + ("..." if len(hcl_content) > 500 else "")
        }
