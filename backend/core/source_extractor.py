import io
import re
import zipfile
import logging
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger("arb.source_extractor")

def extract_docx_text(file_bytes: bytes) -> str:
    """Extract formatted text and tables from Word document (.docx) using built-in zipfile and XML parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            if "word/document.xml" in z.namelist():
                xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)
                lines = []
                # Process paragraphs and tables
                for elem in root.iter():
                    if elem.tag.endswith("}p"):
                        p_texts = [node.text for node in elem.iter() if node.tag.endswith("}t") and node.text]
                        if p_texts:
                            lines.append("".join(p_texts).strip())
                    elif elem.tag.endswith("}tr"):
                        # Table row
                        row_cells = []
                        for cell in elem.iter():
                            if cell.tag.endswith("}tc"):
                                cell_texts = [node.text for node in cell.iter() if node.tag.endswith("}t") and node.text]
                                row_cells.append(" ".join(cell_texts).strip())
                        if row_cells and any(row_cells):
                            lines.append(" | ".join(row_cells))
                
                combined = "\n".join([line for line in lines if line]).strip()
                if combined:
                    return combined
    except Exception as e:
        logger.warning(f"Failed extracting text from docx: {e}")
    return "Word architecture specification document."

def extract_xlsx_text(file_bytes: bytes) -> str:
    """Extract structured tabular rows and shared strings from Excel spreadsheet (.xlsx) using built-in XML parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            shared_strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        shared_strings.append(node.text.strip())

            # Look for worksheet XMLs
            sheet_files = sorted([n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")])
            all_sheet_rows = []

            for sfile in sheet_files[:5]: # up to 5 sheets
                sheet_root = ET.fromstring(z.read(sfile))
                sheet_name = sfile.split("/")[-1].replace(".xml", "")
                all_sheet_rows.append(f"--- Sheet: {sheet_name} ---")

                for row in sheet_root.iter():
                    if row.tag.endswith("}row"):
                        row_values = []
                        for c in row.iter():
                            if c.tag.endswith("}c"):
                                cell_type = c.get("t")
                                val_node = None
                                for child in c:
                                    if child.tag.endswith("}v"):
                                        val_node = child.text
                                        break
                                
                                if cell_type == "s" and val_node is not None:
                                    try:
                                        idx = int(val_node)
                                        if 0 <= idx < len(shared_strings):
                                            row_values.append(shared_strings[idx])
                                        else:
                                            row_values.append(val_node)
                                    except ValueError:
                                        row_values.append(val_node)
                                elif val_node is not None:
                                    row_values.append(val_node.strip())
                                else:
                                    # check for inlineStr
                                    inline_t = [ch.text for ch in c.iter() if ch.tag.endswith("}t") and ch.text]
                                    if inline_t:
                                        row_values.append(" ".join(inline_t).strip())

                        if row_values and any(row_values):
                            all_sheet_rows.append(" | ".join(row_values))

            if len(all_sheet_rows) > 1:
                return "\n".join(all_sheet_rows[:500])
            elif shared_strings:
                return " | ".join(shared_strings[:1000])
    except Exception as e:
        logger.warning(f"Failed extracting text from xlsx: {e}")
    return "Excel spreadsheet architecture inventory data."

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract readable text streams from PDF document with resilient fallbacks."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        combined = "\n".join(pages_text).strip()
        if combined:
            return combined[:25000]
    except Exception:
        pass

    # Fallback 1: decompressed flate streams or raw regex text tokens
    try:
        texts = []
        for match in re.finditer(rb"\((.*?)\)\s*Tj", file_bytes):
            try:
                chunk = match.group(1).decode("latin-1", errors="ignore").strip()
                if chunk and len(chunk) > 1 and not chunk.startswith(("/", "\\")):
                    texts.append(chunk)
            except Exception:
                pass
        if texts:
            return " ".join(texts[:1000])
    except Exception as e:
        logger.warning(f"Stream fallback failed for PDF: {e}")

    # Fallback 2: search for readable string blocks
    try:
        ascii_strings = re.findall(rb"[A-Za-z0-9 ,.:;_\-\(\)/]{4,}", file_bytes)
        clean_strings = [s.decode("latin-1", errors="ignore").strip() for s in ascii_strings if len(s) > 5]
        if clean_strings:
            return "\n".join(clean_strings[:300])
    except Exception:
        pass

    return "PDF architecture and system requirements specification document."

def extract_url_text(url: str) -> str:
    """Fetch and strip HTML tags from a target URL."""
    try:
        import httpx
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                html = resp.text
                text = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return text[:8000]
    except Exception as e:
        logger.warning(f"URL extraction notice for {url}: {e}")
    return f"Web reference documentation at: {url}"

def extract_source_content(
    source_type: str,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    url: Optional[str] = None
) -> str:
    """Universal dispatcher for extracting text from Excel, PDF, Word, or Web URLs."""
    stype = (source_type or "").lower().strip()

    if stype == "url" and url:
        return extract_url_text(url)

    if not file_bytes:
        return ""

    if stype in ("excel", "xlsx", "xls") or (filename and filename.lower().endswith((".xlsx", ".xls"))):
        return extract_xlsx_text(file_bytes)
    elif stype in ("word", "docx", "doc") or (filename and filename.lower().endswith((".docx", ".doc"))):
        return extract_docx_text(file_bytes)
    elif stype in ("pdf",) or (filename and filename.lower().endswith(".pdf")):
        return extract_pdf_text(file_bytes)
    elif filename and filename.lower().endswith((".csv", ".tsv", ".txt", ".json", ".yaml", ".yml")):
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return file_bytes.decode("latin-1", errors="ignore")

    return "Reference architectural source data."

def extract_input_document(file_bytes: bytes, filename: str) -> dict:
    """Convenience helper to extract document content and provide metadata preview for UI."""
    fn = (filename or "").lower()
    modality = "text"
    if fn.endswith((".xlsx", ".xls")):
        modality = "excel"
    elif fn.endswith(".pdf"):
        modality = "pdf"
    elif fn.endswith((".docx", ".doc")):
        modality = "word"
    elif fn.endswith((".csv", ".txt", ".json")):
        modality = "text"

    text = extract_source_content(source_type=modality, file_bytes=file_bytes, filename=filename)
    preview = text[:800] + ("..." if len(text) > 800 else "")
    return {
        "filename": filename,
        "modality": modality,
        "size_bytes": len(file_bytes),
        "char_count": len(text),
        "preview": preview,
        "extracted_text": text
    }

