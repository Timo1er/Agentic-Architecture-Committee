import re
import base64
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

class DiagramParser:
    """Parses architecture diagrams in Mermaid.js syntax, Draw.io XML format, or Image/PDF visual assets."""

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

    @staticmethod
    def parse_image_or_pdf(data_uri_or_base64: str, mime_type: Optional[str] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """Parses visual architecture assets (PNG, JPEG, PDF) for multimodal LLM processing."""
        # Extract MIME type from data URI if present (e.g. data:image/png;base64,iVBORw...)
        inferred_mime = mime_type or "image/png"
        raw_b64 = data_uri_or_base64

        if data_uri_or_base64.startswith("data:"):
            header, _, data = data_uri_or_base64.partition(",")
            raw_b64 = data
            m = re.search(r'data:([^;]+);base64', header)
            if m:
                inferred_mime = m.group(1).lower()

        # Determine asset category
        is_pdf = "pdf" in inferred_mime or (filename and filename.lower().endswith(".pdf"))
        asset_type = "pdf_diagram" if is_pdf else "image_diagram"

        # Calculate approximate byte size
        try:
            byte_length = len(base64.b64decode(raw_b64[:100] + "==")) if raw_b64 else 0
            approx_kb = round((len(raw_b64) * 3 / 4) / 1024, 1)
        except Exception:
            approx_kb = 0

        return {
            "type": asset_type,
            "mime_type": inferred_mime,
            "filename": filename or ("architecture_diagram.pdf" if is_pdf else "architecture_diagram.png"),
            "approx_size_kb": approx_kb,
            "has_multimodal_payload": bool(raw_b64),
            "image_base64_sample": raw_b64[:60] + "..." if len(raw_b64) > 60 else raw_b64,
            "raw_data_uri": data_uri_or_base64 if data_uri_or_base64.startswith("data:") else f"data:{inferred_mime};base64,{raw_b64}",
            "description": f"Visual {inferred_mime.upper()} architecture diagram submitted for multimodal analysis."
        }

    @classmethod
    def parse(cls, input_data: str, input_format: str = "mermaid", mime_type: Optional[str] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        fmt = input_format.lower()
        if fmt in ["image", "png", "jpeg", "jpg", "pdf"] or input_data.startswith("data:image/") or input_data.startswith("data:application/pdf"):
            return cls.parse_image_or_pdf(input_data, mime_type=mime_type, filename=filename)
        elif fmt in ["drawio", "xml"] or "<mxGraphModel" in input_data:
            return cls.parse_drawio(input_data)
        return cls.parse_mermaid(input_data)
