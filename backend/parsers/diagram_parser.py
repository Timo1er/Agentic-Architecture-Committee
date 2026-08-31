import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

class DiagramParser:
    """Parses architecture diagrams in Mermaid.js syntax, Draw.io XML format, or raw image prompts."""

    @staticmethod
    def parse_mermaid(mermaid_code: str) -> Dict[str, Any]:
        """Extracts nodes, edges, subgraphs, and directional flows from Mermaid.js syntax."""
        nodes = set()
        edges = []
        subgraphs = []

        lines = [line.strip() for line in mermaid_code.strip().splitlines() if line.strip()]
        diagram_type = lines[0] if lines else "graph TD"

        # Regex for node declarations and connections
        edge_pattern = re.compile(r'([A-Za-z0-9_\-]+)\s*(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?\s*(-->|---|-.->|==>)\s*(?:\|(.*?)\|)?\s*([A-Za-z0-9_\-]+)\s*(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?')
        subgraph_pattern = re.compile(r'subgraph\s+([A-Za-z0-9_\-\s]+)(?:\[(.*?)\])?')

        current_subgraph = None
        for line in lines:
            if "subgraph" in line:
                m = subgraph_pattern.search(line)
                if m:
                    current_subgraph = m.group(1).strip()
                    subgraphs.append(current_subgraph)
            elif line == "end":
                current_subgraph = None
            else:
                match = edge_pattern.search(line)
                if match:
                    src_id = match.group(1)
                    src_label = match.group(2) or match.group(3) or match.group(4) or src_id
                    rel_type = match.group(5)
                    rel_label = match.group(6) or ""
                    tgt_id = match.group(7)
                    tgt_label = match.group(8) or match.group(9) or match.group(10) or tgt_id

                    nodes.add((src_id, src_label))
                    nodes.add((tgt_id, tgt_label))
                    edges.append({
                        "from": {"id": src_id, "label": src_label},
                        "to": {"id": tgt_id, "label": tgt_label},
                        "relation": rel_type,
                        "label": rel_label,
                        "subgraph": current_subgraph
                    })

        return {
            "type": "mermaid",
            "diagram_type": diagram_type,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": [{"id": n[0], "label": n[1]} for n in nodes],
            "edges": edges,
            "subgraphs": subgraphs,
            "raw_text": mermaid_code
        }

    @staticmethod
    def parse_drawio(xml_content: str) -> Dict[str, Any]:
        """Extracts cell components, labels, and connections from Draw.io / diagrams.net XML."""
        nodes = []
        edges = []
        try:
            root = ET.fromstring(xml_content)
            for cell in root.iter("mxCell"):
                cell_id = cell.get("id")
                value = cell.get("value", "").strip()
                source = cell.get("source")
                target = cell.get("target")

                if source and target:
                    edges.append({
                        "id": cell_id,
                        "source": source,
                        "target": target,
                        "label": value
                    })
                elif value:
                    nodes.append({
                        "id": cell_id,
                        "label": value
                    })

            return {
                "type": "drawio_xml",
                "node_count": len(nodes),
                "edge_count": len(edges),
                "nodes": nodes,
                "edges": edges,
                "raw_text": xml_content[:500] + "... (truncated XML)"
            }
        except Exception as e:
            return {
                "type": "drawio_error",
                "error": f"Failed to parse Draw.io XML: {str(e)}",
                "raw_text": xml_content
            }

    @classmethod
    def parse(cls, input_data: str, input_format: str = "mermaid") -> Dict[str, Any]:
        if input_format.lower() in ["drawio", "xml"] or "<mxGraphModel" in input_data:
            return cls.parse_drawio(input_data)
        return cls.parse_mermaid(input_data)
