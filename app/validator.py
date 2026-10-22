from typing import Dict, Set, List
from app.schemas import DocumentTree, ValidationResult, NodeType


class DocumentTreeValidator:
    """
    Validates structural consistency, parent-child reciprocity, page coverage,
    and semantic integrity of a parsed DocumentTree.
    """

    @classmethod
    def validate(cls, tree: DocumentTree, raise_on_error: bool = False) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        
        # 1. Root Node Check
        if not tree.root_node_id:
            errors.append("DocumentTree root_node_id is empty.")
        elif tree.root_node_id not in tree.nodes:
            errors.append(f"Root node '{tree.root_node_id}' does not exist in nodes dictionary.")
        else:
            root_node = tree.nodes[tree.root_node_id]
            if root_node.parent_id is not None:
                errors.append(f"Root node '{tree.root_node_id}' must not have a parent_id (found: {root_node.parent_id}).")

        # 2. Check for Orphan Nodes and ID Consistency
        all_ids: Set[str] = set()
        pages_with_content: Set[int] = set()

        for node_id, node in tree.nodes.items():
            if node_id != node.id:
                errors.append(f"Dict key '{node_id}' does not match node.id '{node.id}'.")
            if node_id in all_ids:
                errors.append(f"Duplicate node ID detected: '{node_id}'.")
            all_ids.add(node_id)

            # Record page numbers
            for p in range(node.page_start, node.page_end + 1):
                pages_with_content.add(p)

            # Page boundaries
            if node.page_start < 1 or node.page_end > tree.total_pages:
                errors.append(f"Node '{node_id}' has invalid page range [{node.page_start}, {node.page_end}] outside [1, {tree.total_pages}].")
            if node.page_start > node.page_end:
                errors.append(f"Node '{node_id}' has page_start ({node.page_start}) > page_end ({node.page_end}).")

            # Check orphan
            if node_id != tree.root_node_id:
                if not node.parent_id:
                    errors.append(f"Orphan node '{node_id}': has no parent_id.")
                elif node.parent_id not in tree.nodes:
                    errors.append(f"Invalid parent_id '{node.parent_id}' for node '{node_id}': parent does not exist in tree.")

            # Content checks
            if not node.title_or_text.strip():
                warnings.append(f"Node '{node_id}' has empty title_or_text.")

            # Table specific checks
            if node.node_type == NodeType.TABLE:
                tbl_data = node.metadata.get("table_data", {})
                rows = tbl_data.get("rows", [])
                headers = tbl_data.get("headers", [])
                if not rows and not headers:
                    errors.append(f"Table node '{node_id}' has neither headers nor rows.")
                elif not headers:
                    warnings.append(f"Table node '{node_id}' has no explicit headers.")

        # 3. Parent-Child Reciprocity & Cycles
        for node_id, node in tree.nodes.items():
            for child_id in node.children_ids:
                if child_id not in tree.nodes:
                    errors.append(f"Node '{node_id}' references non-existent child '{child_id}'.")
                else:
                    child = tree.nodes[child_id]
                    if child.parent_id != node_id:
                        errors.append(f"Reciprocity failure: Node '{node_id}' lists child '{child_id}', but child's parent_id is '{child.parent_id}'.")

        # 4. Reachability & Cycle Detection
        if tree.root_node_id in tree.nodes:
            visited: Set[str] = set()
            rec_stack: Set[str] = set()

            def check_cycles(curr_id: str) -> None:
                visited.add(curr_id)
                rec_stack.add(curr_id)
                for c_id in tree.nodes[curr_id].children_ids:
                    if c_id not in visited:
                        check_cycles(c_id)
                    elif c_id in rec_stack:
                        errors.append(f"Cycle detected involving node '{curr_id}' and child '{c_id}'.")
                rec_stack.remove(curr_id)

            check_cycles(tree.root_node_id)

            unreachable = all_ids - visited
            if unreachable:
                errors.append(f"Unreachable nodes from root: {sorted(list(unreachable))}")

        # 5. Page-level Extraction Coverage
        missing_pages = set(range(1, tree.total_pages + 1)) - pages_with_content
        if missing_pages:
            errors.append(f"Page extraction failure: Pages {sorted(list(missing_pages))} have zero extracted content.")

        # 6. Reading Order Verification
        reading_set = set(tree.reading_order)
        if len(tree.reading_order) != len(reading_set):
            errors.append("Duplicate entries found in reading_order list.")
        missing_from_reading = all_ids - reading_set
        if missing_from_reading:
            warnings.append(f"Nodes missing from reading_order: {sorted(list(missing_from_reading))}")

        # Calculate statistics
        stats = {
            "total_nodes": len(tree.nodes),
            "sections_count": sum(1 for n in tree.nodes.values() if n.node_type == NodeType.SECTION),
            "paragraphs_count": sum(1 for n in tree.nodes.values() if n.node_type == NodeType.PARAGRAPH),
            "tables_count": sum(1 for n in tree.nodes.values() if n.node_type == NodeType.TABLE),
            "lists_count": sum(1 for n in tree.nodes.values() if n.node_type in (NodeType.LIST, NodeType.LIST_ITEM)),
            "pages_covered": len(pages_with_content),
            "total_pages": tree.total_pages,
            "uncertain_nodes_count": sum(1 for n in tree.nodes.values() if n.is_uncertain)
        }

        result = ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            stats=stats
        )

        if raise_on_error and not result.is_valid:
            raise ValueError(f"DocumentTree validation failed: {'; '.join(errors)}")

        return result
