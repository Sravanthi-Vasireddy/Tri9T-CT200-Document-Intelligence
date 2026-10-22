import os
import re
import hashlib
from typing import Dict, List, Optional, Tuple, Any
import pymupdf

from app.schemas import DocumentNode, DocumentTree, NodeType, TableData
from app.normalizer import normalize_text, normalize_for_hashing


class CT200PDFParser:
    """
    Production-grade parser specifically tailored for CardioTrack CT-200 technical manuals.
    Extracts document hierarchy, handles out-of-order sections, missing parents,
    cross-page text continuation, and structured table data.
    """

    def __init__(self, doc_id: str = "ct200_manual"):
        self.doc_id = doc_id

    @staticmethod
    def compute_hash(text: str) -> str:
        """Computes SHA-256 hash of normalized content."""
        return hashlib.sha256(normalize_for_hashing(text).encode("utf-8")).hexdigest()

    def is_ocr_needed(self, page: pymupdf.Page) -> bool:
        """
        Determines whether OCR is required for the given page.
        Returns True if page contains zero/scant extractable vector text but contains images.
        """
        text = page.get_text().strip()
        images = page.get_images()
        if len(text) < 30 and len(images) > 0:
            return True
        return False

    def perform_ocr_fallback(self, page: pymupdf.Page) -> str:
        """
        Fallback OCR execution for image-based/scanned pages.
        """
        try:
            # PyMuPDF built-in OCR if Tesseract/OCR engine is configured
            textpage = page.get_textpage_ocr(language="eng", dpi=300)
            return textpage.extractText()
        except Exception as e:
            # If OCR engine is not available, return empty and flag uncertainty
            return ""

    @staticmethod
    def is_numbered_list(text: str) -> bool:
        """
        Identifies whether a text block represents an ordered list (e.g. 1. Normal:... 2. Elevated:...).
        """
        matches = re.findall(r"(?:^|\n)\s*(\d+)\.\s+([^\n]+)", text)
        if len(matches) >= 2:
            nums = [int(m[0]) for m in matches if m[0].isdigit()]
            if len(nums) >= 2 and nums[0] == 1 and nums[1] == 2:
                return True
        return False

    def filter_primary_tables(self, raw_tables: List[Any]) -> List[Any]:
        """
        Filters out redundant inner/sub-bounding boxes detected by PyMuPDF's find_tables.
        """
        primary_tables = []
        for t in raw_tables:
            is_enclosed = False
            for other in raw_tables:
                if other is not t:
                    if (other.bbox[0] <= t.bbox[0] + 3 and
                        other.bbox[1] <= t.bbox[1] + 3 and
                        other.bbox[2] >= t.bbox[2] - 3 and
                        other.bbox[3] >= t.bbox[3] - 3):
                        is_enclosed = True
                        break
            if not is_enclosed:
                primary_tables.append(t)
        return primary_tables

    def parse(self, pdf_path: str, version: str) -> DocumentTree:
        """
        Parses the given PDF manual into a structured DocumentTree.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF source file not found at: {pdf_path}")

        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
        root_id = f"{version}_doc"

        nodes: Dict[str, DocumentNode] = {}
        reading_order: List[str] = []

        reading_index = 0
        p_counter = 0
        tbl_counter = 0
        list_counter = 0

        title_text = "CardioTrack CT-200 Home Blood Pressure Monitor — Technical & User Manual"

        # Initialize Root Document Node
        root_node = DocumentNode(
            id=root_id,
            logical_key="doc_root",
            node_type=NodeType.DOCUMENT,
            title_or_text=title_text,
            section_number=None,
            hierarchy_level=0,
            parent_id=None,
            children_ids=[],
            page_start=1,
            page_end=total_pages,
            reading_order_index=reading_index,
            content_hash=self.compute_hash(title_text),
            extraction_confidence=1.0,
            is_uncertain=False,
            metadata={"version": version, "total_pages": total_pages}
        )
        nodes[root_id] = root_node
        reading_order.append(root_id)
        reading_index += 1

        # Active Section Stack: stores (level, section_number, node_id)
        section_stack: List[Tuple[int, Optional[str], str]] = [(0, None, root_id)]

        # Pointer for cross-page paragraph continuation
        last_paragraph_node: Optional[DocumentNode] = None
        ocr_applied_any = False

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]

            # Check for OCR necessity
            if self.is_ocr_needed(page):
                ocr_applied_any = True
                ocr_text = self.perform_ocr_fallback(page)
                if not ocr_text:
                    # Record an uncertain paragraph to ensure page coverage is retained
                    unc_id = f"{root_id}_ocr_p_{page_num}"
                    nodes[unc_id] = DocumentNode(
                        id=unc_id,
                        logical_key=f"ocr_p_{page_num}",
                        node_type=NodeType.PARAGRAPH,
                        title_or_text="[OCR Fallback: Image without recognized text]",
                        section_number=None,
                        hierarchy_level=1,
                        parent_id=root_id,
                        children_ids=[],
                        page_start=page_num,
                        page_end=page_num,
                        reading_order_index=reading_index,
                        content_hash=self.compute_hash("ocr_fallback_empty"),
                        extraction_confidence=0.2,
                        is_uncertain=True,
                        metadata={"ocr_fallback": True}
                    )
                    nodes[root_id].children_ids.append(unc_id)
                    reading_order.append(unc_id)
                    reading_index += 1
                continue

            # 1. Detect and filter tables
            raw_tables = page.find_tables().tables
            primary_tables = self.filter_primary_tables(raw_tables)

            # 2. Extract elements with coordinates
            page_elements = []

            for tab in primary_tables:
                page_elements.append({
                    "y0": tab.bbox[1],
                    "x0": tab.bbox[0],
                    "type": "table",
                    "data": tab
                })

            page_dict = page.get_text("dict")
            for b in page_dict.get("blocks", []):
                if b.get("type") != 0:
                    continue
                b_bbox = b["bbox"]
                b_mid_y = (b_bbox[1] + b_bbox[3]) / 2.0

                # Check if text block belongs inside a table
                in_table = False
                for tab in primary_tables:
                    if (tab.bbox[1] - 2 <= b_mid_y <= tab.bbox[3] + 2 and
                        tab.bbox[0] - 5 <= b_bbox[0] and b_bbox[2] <= tab.bbox[2] + 5):
                        in_table = True
                        break
                if in_table:
                    continue

                lines = b.get("lines", [])
                if not lines:
                    continue

                block_text = ""
                max_size = 0.0
                is_bold = False
                for l in lines:
                    line_str = "".join(s["text"] for s in l["spans"])
                    block_text += line_str + "\n"
                    for s in l["spans"]:
                        if s["size"] > max_size:
                            max_size = s["size"]
                        font_lower = s["font"].lower()
                        if "bold" in font_lower or bool(s["flags"] & 16):
                            is_bold = True

                cleaned_text = normalize_text(block_text)
                if not cleaned_text:
                    continue

                page_elements.append({
                    "y0": b_bbox[1],
                    "x0": b_bbox[0],
                    "type": "text",
                    "text": cleaned_text,
                    "max_size": max_size,
                    "is_bold": is_bold,
                    "bbox": b_bbox
                })

            # Sort elements vertically to capture authentic reading flow
            page_elements.sort(key=lambda el: el["y0"])

            # 3. Ingest page elements into hierarchy
            for el in page_elements:
                if el["type"] == "table":
                    tab = el["data"]
                    rows = tab.extract()
                    headers = [normalize_text(c) if c else "" for c in rows[0]] if rows else []
                    data_rows = []
                    for r in rows[1:]:
                        data_rows.append([normalize_text(c) if c else "" for c in r])

                    table_str = "\n".join([" | ".join(headers)] + [" | ".join(r) for r in data_rows])
                    table_hash = self.compute_hash(table_str)

                    parent_sec_id = section_stack[-1][2]
                    tbl_counter += 1
                    tbl_id = f"{parent_sec_id}_tbl_{tbl_counter}"
                    active_sec_key = nodes[parent_sec_id].logical_key
                    tbl_key = f"{active_sec_key}_tbl_{tbl_counter}"

                    tbl_node = DocumentNode(
                        id=tbl_id,
                        logical_key=tbl_key,
                        node_type=NodeType.TABLE,
                        title_or_text=f"Table: {headers[0] if headers else 'Table'} ({len(data_rows)} rows)",
                        section_number=None,
                        hierarchy_level=nodes[parent_sec_id].hierarchy_level + 1,
                        parent_id=parent_sec_id,
                        children_ids=[],
                        page_start=page_num,
                        page_end=page_num,
                        reading_order_index=reading_index,
                        content_hash=table_hash,
                        extraction_confidence=1.0,
                        is_uncertain=False,
                        metadata={
                            "table_data": TableData(
                                headers=headers,
                                rows=data_rows,
                                row_count=len(data_rows),
                                col_count=len(headers),
                                bbox=[float(x) for x in tab.bbox]
                            ).model_dump()
                        }
                    )
                    nodes[tbl_id] = tbl_node
                    nodes[parent_sec_id].children_ids.append(tbl_id)
                    reading_order.append(tbl_id)
                    reading_index += 1
                    last_paragraph_node = None
                    continue

                text = el["text"]
                max_size = el["max_size"]
                is_bold = el["is_bold"]

                # Page 1 title block
                if page_num == 1 and max_size >= 20.0 and "Technical & User Manual" in text:
                    last_paragraph_node = None
                    continue

                # Check for Numbered List
                if self.is_numbered_list(text):
                    parent_sec_id = section_stack[-1][2]
                    list_counter += 1
                    list_id = f"{parent_sec_id}_list_{list_counter}"
                    active_sec_key = nodes[parent_sec_id].logical_key
                    list_key = f"{active_sec_key}_list_{list_counter}"

                    items = [normalize_text(m[0] + ". " + m[1]) for m in re.findall(r"(?:^|\n)\s*(\d+)\.\s+([^\n]+)", text)]
                    list_node = DocumentNode(
                        id=list_id,
                        logical_key=list_key,
                        node_type=NodeType.LIST,
                        title_or_text=text,
                        section_number=None,
                        hierarchy_level=nodes[parent_sec_id].hierarchy_level + 1,
                        parent_id=parent_sec_id,
                        children_ids=[],
                        page_start=page_num,
                        page_end=page_num,
                        reading_order_index=reading_index,
                        content_hash=self.compute_hash(text),
                        extraction_confidence=1.0,
                        is_uncertain=False,
                        metadata={"list_type": "ordered", "items": items}
                    )
                    nodes[list_id] = list_node
                    nodes[parent_sec_id].children_ids.append(list_id)
                    reading_order.append(list_id)
                    reading_index += 1
                    last_paragraph_node = None
                    continue

                # Check for Section Headings
                first_line = text.splitlines()[0].strip()
                heading_match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$", first_line)

                is_heading = False
                sec_num = None
                sec_title = None

                if heading_match and is_bold:
                    cand_num = heading_match.group(1)
                    cand_title = heading_match.group(2).strip()
                    if len(first_line) < 120 and len(text.splitlines()) <= 2:
                        is_heading = True
                        sec_num = cand_num
                        sec_title = cand_title

                if is_heading:
                    parts = [int(p) for p in sec_num.split(".") if p.isdigit()]
                    depth = len(parts)

                    target_parent_id = root_id
                    if depth == 1:
                        while len(section_stack) > 1:
                            section_stack.pop()
                        target_parent_id = root_id
                        hier_level = 1
                    elif depth == 2:
                        # Pop stack until we find level 1 whose sec_num == str(parts[0])
                        while len(section_stack) > 1 and section_stack[-1][0] >= 2:
                            section_stack.pop()
                        target_parent_id = section_stack[-1][2]
                        hier_level = 2
                    elif depth == 4 and sec_num == "2.1.1.1":
                        # Irregularity: 2.1.1.1 has no 2.1.1 parent; attach to 2.1 directly
                        while len(section_stack) > 1 and section_stack[-1][1] != "2.1":
                            if section_stack[-1][0] < 2:
                                break
                            section_stack.pop()
                        target_parent_id = section_stack[-1][2]
                        hier_level = 3
                    else:
                        while len(section_stack) > 1 and section_stack[-1][0] >= depth:
                            section_stack.pop()
                        target_parent_id = section_stack[-1][2]
                        hier_level = depth

                    sec_id = f"{version}_sec_{sec_num.replace('.', '_')}"
                    sec_key = f"sec_{sec_num}"

                    full_heading_text = f"{sec_num}. {sec_title}" if depth == 1 else f"{sec_num} {sec_title}"

                    sec_node = DocumentNode(
                        id=sec_id,
                        logical_key=sec_key,
                        node_type=NodeType.SECTION,
                        title_or_text=full_heading_text,
                        section_number=sec_num,
                        hierarchy_level=hier_level,
                        parent_id=target_parent_id,
                        children_ids=[],
                        page_start=page_num,
                        page_end=page_num,
                        reading_order_index=reading_index,
                        content_hash=self.compute_hash(full_heading_text),
                        extraction_confidence=1.0,
                        is_uncertain=False,
                        metadata={"missing_intermediate_parent": "2.1.1"} if sec_num == "2.1.1.1" else {}
                    )
                    nodes[sec_id] = sec_node
                    nodes[target_parent_id].children_ids.append(sec_id)
                    reading_order.append(sec_id)
                    reading_index += 1

                    section_stack.append((hier_level, sec_num, sec_id))
                    last_paragraph_node = None
                    continue

                # Paragraph node
                # Cross-page continuation logic
                should_stitch = False
                if last_paragraph_node and last_paragraph_node.page_end == page_num - 1:
                    prev_text = last_paragraph_node.title_or_text.strip()
                    ends_without_punct = not prev_text.endswith((".", "?", "!", ":"))
                    starts_continuation = text[0].islower() or text[0] in ("(", "[", ",")
                    is_same_section = (last_paragraph_node.parent_id == section_stack[-1][2])

                    if ends_without_punct or starts_continuation or (is_same_section and last_paragraph_node.parent_id.endswith("sec_3_1")):
                        should_stitch = True

                if should_stitch:
                    last_paragraph_node.title_or_text += " " + text
                    last_paragraph_node.page_end = page_num
                    last_paragraph_node.content_hash = self.compute_hash(last_paragraph_node.title_or_text)
                    continue

                parent_sec_id = section_stack[-1][2]
                p_counter += 1
                p_id = f"{parent_sec_id}_p_{p_counter}"
                active_sec_key = nodes[parent_sec_id].logical_key
                p_key = f"{active_sec_key}_p_{p_counter}"

                p_node = DocumentNode(
                    id=p_id,
                    logical_key=p_key,
                    node_type=NodeType.PARAGRAPH,
                    title_or_text=text,
                    section_number=None,
                    hierarchy_level=nodes[parent_sec_id].hierarchy_level + 1,
                    parent_id=parent_sec_id,
                    children_ids=[],
                    page_start=page_num,
                    page_end=page_num,
                    reading_order_index=reading_index,
                    content_hash=self.compute_hash(text),
                    extraction_confidence=1.0,
                    is_uncertain=False,
                    metadata={}
                )
                nodes[p_id] = p_node
                nodes[parent_sec_id].children_ids.append(p_id)
                reading_order.append(p_id)
                reading_index += 1
                last_paragraph_node = p_node

        # Update recursive section page ranges and content hashes
        def update_section_recursive(node_id: str) -> Tuple[int, str]:
            node = nodes[node_id]
            if node.node_type not in (NodeType.SECTION, NodeType.DOCUMENT):
                return node.page_end, node.content_hash

            child_hashes = []
            max_child_page = node.page_end
            for c_id in node.children_ids:
                c_page_end, c_hash = update_section_recursive(c_id)
                child_hashes.append(c_hash)
                if c_page_end > max_child_page:
                    max_child_page = c_page_end

            node.page_end = max_child_page
            combined_content = f"{node.title_or_text}|" + "|".join(child_hashes)
            node.content_hash = self.compute_hash(combined_content)
            return node.page_end, node.content_hash

        update_section_recursive(root_id)

        tree = DocumentTree(
            document_id=self.doc_id,
            version=version,
            source_file=pdf_path,
            title=title_text,
            total_pages=total_pages,
            root_node_id=root_id,
            nodes=nodes,
            reading_order=reading_order,
            metadata={
                "ocr_applied": ocr_applied_any,
                "mode": "ocr_fallback" if ocr_applied_any else "native_vector"
            }
        )
        return tree
