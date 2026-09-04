import html
import uuid
from typing import List, Dict, Any, Optional

CLOUD_THEMES = {
    "AWS": {
        "primary": "#FF9900",
        "secondary": "#232F3E",
        "bg_container": "#141F2E",
        "border": "#FF9900",
        "header_fill": "#232F3E",
        "card_fill": "#1E293B",
        "text": "#FFFFFF",
        "subtext": "#FF9900"
    },
    "GCP": {
        "primary": "#4285F4",
        "secondary": "#34A853",
        "bg_container": "#111827",
        "border": "#4285F4",
        "header_fill": "#1E3A8A",
        "card_fill": "#1E293B",
        "text": "#FFFFFF",
        "subtext": "#60A5FA"
    },
    "Azure": {
        "primary": "#0078D4",
        "secondary": "#005BA1",
        "bg_container": "#0B192C",
        "border": "#0078D4",
        "header_fill": "#004578",
        "card_fill": "#1E293B",
        "text": "#FFFFFF",
        "subtext": "#38BDF8"
    },
    "AliCloud": {
        "primary": "#FF6A00",
        "secondary": "#CC5500",
        "bg_container": "#1A1412",
        "border": "#FF6A00",
        "header_fill": "#2E1F1A",
        "card_fill": "#1E293B",
        "text": "#FFFFFF",
        "subtext": "#FB923C"
    },
    "OVH": {
        "primary": "#00539B",
        "secondary": "#000E9C",
        "bg_container": "#0D1B2A",
        "border": "#00539B",
        "header_fill": "#0A2540",
        "card_fill": "#1E293B",
        "text": "#FFFFFF",
        "subtext": "#38BDF8"
    },
    "Multi-Cloud": {
        "primary": "#818CF8",
        "secondary": "#38BDF8",
        "bg_container": "#131722",
        "border": "#818CF8",
        "header_fill": "#1E1E38",
        "card_fill": "#1E293B",
        "text": "#FFFFFF",
        "subtext": "#A5B4FC"
    }
}

class DrawIOGenerator:
    """Generates standard Draw.io / diagrams.net mxGraphModel XML for cloud architectures."""

    @classmethod
    def generate_xml(
        cls,
        title: str,
        cloud_provider: str,
        components: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, str]]] = None
    ) -> str:
        theme = CLOUD_THEMES.get(cloud_provider, CLOUD_THEMES["Multi-Cloud"])
        escaped_title = html.escape(title)
        diag_id = str(uuid.uuid4())[:8]

        tier_order = [
            ("Edge & Ingress", "Public Subnet / Ingress DMZ", 50, 120),
            ("Application / Compute", "Private App Subnet (Compute Tier)", 450, 120),
            ("Database & State", "Secure Data Subnet (Storage & DB)", 850, 120),
            ("Messaging & Async", "Event Streaming & Caching Bus", 450, 480),
            ("Security & Observability", "Zero-Trust & Telemetry Control Plane", 850, 480)
        ]

        tier_map: Dict[str, List[Dict[str, Any]]] = {t[0]: [] for t in tier_order}
        for comp in components:
            raw_tier = comp.get("tier", "").strip()
            matched = False
            for t_key, _, _, _ in tier_order:
                if t_key.lower() in raw_tier.lower() or raw_tier.lower() in t_key.lower():
                    tier_map[t_key].append(comp)
                    matched = True
                    break
            if not matched:
                tier_map["Application / Compute"].append(comp)

        xml_parts = []
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<mxfile host="app.diagrams.net" modified="2026-09-04T00:00:00.000Z" agent="ARB Multi-Agent Architecture Platform" version="24.0.0" type="device">')
        xml_parts.append(f'  <diagram id="{diag_id}" name="{escaped_title}">')
        xml_parts.append('    <mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1800" pageHeight="1100" background="#0f172a" math="0" shadow="1">')
        xml_parts.append('      <root>')
        xml_parts.append('        <mxCell id="0"/>')
        xml_parts.append('        <mxCell id="1" parent="0"/>')

        cell_id = 2

        # 1. Main Architecture Header Title Card
        header_val = f"&lt;b style='font-size:16px;'&gt;{escaped_title}&lt;/b&gt;&lt;br/&gt;&lt;span style='color:{theme['subtext']};font-size:12px;'&gt;Target Cloud: {cloud_provider} | Architecture Decision &amp; Topology Matrix&lt;/span&gt;"
        header_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={theme['header_fill']};strokeColor={theme['border']};strokeWidth=2;fontColor={theme['text']};arcSize=10;"
        xml_parts.append(f'        <mxCell id="{cell_id}" value="{header_val}" style="{header_style}" vertex="1" parent="1">')
        xml_parts.append('          <mxGeometry x="50" y="30" width="1250" height="55" as="geometry"/>')
        xml_parts.append('        </mxCell>')
        cell_id += 1

        tier_container_ids = {}

        # 2. Render Tier Containers (Swimlanes / Subnets)
        for tier_key, container_name, x, y in tier_order:
            cont_id = cell_id
            tier_container_ids[tier_key] = cont_id
            cell_id += 1
            
            c_val = f"&lt;b style='font-size:13px;'&gt;{html.escape(container_name)}&lt;/b&gt;"
            c_style = f"swimlane;startSize=28;horizontal=1;swimlaneFillColor={theme['card_fill']};fillColor={theme['header_fill']};strokeColor={theme['border']};strokeWidth=1.5;dashed=1;arcSize=8;fontColor={theme['text']};fontStyle=1;"
            w = 360
            h = 320
            xml_parts.append(f'        <mxCell id="{cont_id}" value="{c_val}" style="{c_style}" vertex="1" parent="1">')
            xml_parts.append(f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>')
            xml_parts.append('        </mxCell>')

            comps_in_tier = tier_map.get(tier_key, [])
            item_y = 45
            for idx, c in enumerate(comps_in_tier[:3]):
                c_node_id = cell_id
                cell_id += 1

                c_name = html.escape(str(c.get("name", "Component")))
                c_svc = html.escape(str(c.get("cloud_service", cloud_provider + " Native Service")))
                c_size = html.escape(str(c.get("sizing", "HA Configured"))[:35])
                c_cost = c.get("monthly_cost_usd", "")
                cost_str = f"&lt;br/&gt;&lt;span style='color:#38bdf8;font-size:10px;'&gt;Est: ${c_cost}/mo&lt;/span&gt;" if c_cost else ""

                item_val = f"&lt;b style='font-size:12px;'&gt;{c_name}&lt;/b&gt;&lt;br/&gt;&lt;span style='color:{theme['subtext']};font-size:11px;'&gt;{c_svc}&lt;/span&gt;&lt;br/&gt;&lt;span style='color:#94a3b8;font-size:10px;'&gt;{c_size}&lt;/span&gt;{cost_str}"
                item_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={theme['card_fill']};strokeColor={theme['border']};strokeWidth=1.5;fontColor={theme['text']};shadow=1;arcSize=10;"

                xml_parts.append(f'        <mxCell id="{c_node_id}" value="{item_val}" style="{item_style}" vertex="1" parent="{cont_id}">')
                xml_parts.append(f'          <mxGeometry x="20" y="{item_y}" width="320" height="75" as="geometry"/>')
                xml_parts.append('        </mxCell>')
                item_y += 85

        # 3. Directed Flow Connectors
        flow_edges = [
            (tier_container_ids.get("Edge & Ingress"), tier_container_ids.get("Application / Compute"), "TLS 1.3 / Ingress Traffic"),
            (tier_container_ids.get("Application / Compute"), tier_container_ids.get("Database & State"), "Encrypted Queries / Pool"),
            (tier_container_ids.get("Application / Compute"), tier_container_ids.get("Messaging & Async"), "Async Events / Pub-Sub"),
            (tier_container_ids.get("Database & State"), tier_container_ids.get("Security & Observability"), "Audit Logs & CMEK KMS")
        ]

        for src, tgt, label in flow_edges:
            if src and tgt:
                edge_id = cell_id
                cell_id += 1
                edge_style = f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeColor={theme['primary']};strokeWidth=2;fontColor=#f8fafc;labelBackgroundColor=#1e293b;endArrow=block;endFill=1;"
                xml_parts.append(f'        <mxCell id="{edge_id}" value="{html.escape(label)}" style="{edge_style}" edge="1" parent="1" source="{src}" target="{tgt}">')
                xml_parts.append('          <mxGeometry relative="1" as="geometry"/>')
                xml_parts.append('        </mxCell>')

        xml_parts.append('      </root>')
        xml_parts.append('    </mxGraphModel>')
        xml_parts.append('  </diagram>')
        xml_parts.append('</mxfile>')

        return "\n".join(xml_parts)
