from typing import Any, Dict, List, Optional, Set, Tuple
from app.schemas import (
    DocumentNode,
    DocumentTree,
    NodeChangeStatus,
    NodeMatch
)


class DocumentVersionMatcher:
    """
    Compares two document version trees (previous version vs. current version)
    to identify unchanged, changed, added, removed, and ambiguous nodes.
    Maintains stable logical keys and uses parent context and hierarchy to disambiguate.
    """

    @classmethod
    def match_versions(
        cls,
        prev_nodes: Dict[str, Any],
        curr_tree: DocumentTree
    ) -> Tuple[List[NodeMatch], Dict[str, int]]:
        """
        Matches curr_tree nodes against prev_nodes.
        prev_nodes can be a dict of DocumentNodeModel or serialized dicts.
        """
        curr_nodes = curr_tree.nodes
        matched_curr_ids: Set[str] = set()
        matched_prev_ids: Set[str] = set()
        matches: List[NodeMatch] = []

        # Helper to get attributes uniformly whether prev_nodes holds models or dicts
        def get_attr(node: Any, key: str, default: Any = None) -> Any:
            if isinstance(node, dict):
                return node.get(key, default)
            return getattr(node, key, default)

        # 1. Match Document Root
        prev_root = None
        for n in prev_nodes.values():
            if get_attr(n, "node_type") == "document" or get_attr(n, "logical_key") == "doc_root":
                prev_root = n
                break

        curr_root = curr_nodes.get(curr_tree.root_node_id)
        if prev_root and curr_root:
            prev_hash = get_attr(prev_root, "content_hash")
            st = NodeChangeStatus.UNCHANGED if prev_hash == curr_root.content_hash else NodeChangeStatus.CHANGED
            matches.append(NodeMatch(
                logical_key=curr_root.logical_key,
                status=st,
                prev_node_id=get_attr(prev_root, "id"),
                curr_node_id=curr_root.id,
                prev_hash=prev_hash,
                curr_hash=curr_root.content_hash,
                node_type=curr_root.node_type.value if hasattr(curr_root.node_type, "value") else str(curr_root.node_type),
                title_or_text=curr_root.title_or_text,
                details="Root document node matched"
            ))
            matched_prev_ids.add(get_attr(prev_root, "id"))
            matched_curr_ids.add(curr_root.id)

        # 2. Index Sections in prev and curr
        prev_sections_by_num: Dict[str, List[Any]] = {}
        for n in prev_nodes.values():
            if get_attr(n, "node_type") == "section":
                s_num = get_attr(n, "section_number")
                if s_num:
                    prev_sections_by_num.setdefault(s_num, []).append(n)

        curr_sections_by_num: Dict[str, List[DocumentNode]] = {}
        for n in curr_nodes.values():
            if n.node_type.value == "section" and n.section_number:
                curr_sections_by_num.setdefault(n.section_number, []).append(n)

        # Match sections by section_number and disambiguate repeated headings using parent context
        for s_num, curr_sec_list in curr_sections_by_num.items():
            prev_sec_list = prev_sections_by_num.get(s_num, [])

            if len(curr_sec_list) == 1 and len(prev_sec_list) == 1:
                # Direct unambiguous section match
                c_sec = curr_sec_list[0]
                p_sec = prev_sec_list[0]
                prev_hash = get_attr(p_sec, "content_hash")
                st = NodeChangeStatus.UNCHANGED if prev_hash == c_sec.content_hash else NodeChangeStatus.CHANGED
                matches.append(NodeMatch(
                    logical_key=c_sec.logical_key,
                    status=st,
                    prev_node_id=get_attr(p_sec, "id"),
                    curr_node_id=c_sec.id,
                    prev_hash=prev_hash,
                    curr_hash=c_sec.content_hash,
                    node_type="section",
                    title_or_text=c_sec.title_or_text,
                    details=f"Section {s_num} matched"
                ))
                matched_prev_ids.add(get_attr(p_sec, "id"))
                matched_curr_ids.add(c_sec.id)

            elif len(curr_sec_list) > 1 or len(prev_sec_list) > 1:
                # Repeated heading disambiguation using parent logical key
                for c_sec in curr_sec_list:
                    # Find candidate in prev_sec_list with matching parent logical key
                    c_parent = curr_nodes.get(c_sec.parent_id)
                    c_parent_key = c_parent.logical_key if c_parent else None

                    candidates = []
                    for p_sec in prev_sec_list:
                        p_parent_id = get_attr(p_sec, "parent_id")
                        p_parent = prev_nodes.get(p_parent_id)
                        p_parent_key = get_attr(p_parent, "logical_key") if p_parent else None
                        if p_parent_key == c_parent_key:
                            candidates.append(p_sec)

                    if len(candidates) == 1:
                        p_sec = candidates[0]
                        prev_hash = get_attr(p_sec, "content_hash")
                        st = NodeChangeStatus.UNCHANGED if prev_hash == c_sec.content_hash else NodeChangeStatus.CHANGED
                        matches.append(NodeMatch(
                            logical_key=c_sec.logical_key,
                            status=st,
                            prev_node_id=get_attr(p_sec, "id"),
                            curr_node_id=c_sec.id,
                            prev_hash=prev_hash,
                            curr_hash=c_sec.content_hash,
                            node_type="section",
                            title_or_text=c_sec.title_or_text,
                            details=f"Repeated section {s_num} disambiguated via parent context ({c_parent_key})"
                        ))
                        matched_prev_ids.add(get_attr(p_sec, "id"))
                        matched_curr_ids.add(c_sec.id)
                    else:
                        # Ambiguous match detected
                        matches.append(NodeMatch(
                            logical_key=c_sec.logical_key,
                            status=NodeChangeStatus.AMBIGUOUS,
                            prev_node_id=None,
                            curr_node_id=c_sec.id,
                            prev_hash=None,
                            curr_hash=c_sec.content_hash,
                            node_type="section",
                            title_or_text=c_sec.title_or_text,
                            details=f"Ambiguous match for section {s_num}: found {len(candidates)} plausible candidates"
                        ))
                        matched_curr_ids.add(c_sec.id)
            else:
                # Section added in current version (not present in prev)
                for c_sec in curr_sec_list:
                    matches.append(NodeMatch(
                        logical_key=c_sec.logical_key,
                        status=NodeChangeStatus.ADDED,
                        prev_node_id=None,
                        curr_node_id=c_sec.id,
                        prev_hash=None,
                        curr_hash=c_sec.content_hash,
                        node_type="section",
                        title_or_text=c_sec.title_or_text,
                        details=f"New section {s_num} added"
                    ))
                    matched_curr_ids.add(c_sec.id)

        # 3. Match Content Nodes (Tables, Lists, Paragraphs) under matched parents
        for m in [m for m in matches if m.status in (NodeChangeStatus.UNCHANGED, NodeChangeStatus.CHANGED)]:
            p_node_id = m.prev_node_id
            c_node_id = m.curr_node_id
            if not p_node_id or not c_node_id:
                continue

            p_node = prev_nodes[p_node_id]
            c_node = curr_nodes[c_node_id]

            # Get content children (ignoring sections which are handled above)
            p_children_ids = get_attr(p_node, "children_ids", [])
            if isinstance(p_children_ids, str):
                import json
                p_children_ids = json.loads(p_children_ids)

            p_content = [prev_nodes[cid] for cid in p_children_ids if cid in prev_nodes and get_attr(prev_nodes[cid], "node_type") != "section"]
            c_content = [curr_nodes[cid] for cid in c_node.children_ids if cid in curr_nodes and curr_nodes[cid].node_type.value != "section"]

            # 3a. Tables
            p_tabs = [c for c in p_content if get_attr(c, "node_type") == "table"]
            c_tabs = [c for c in c_content if c.node_type.value == "table"]
            for i, c_tab in enumerate(c_tabs):
                if i < len(p_tabs):
                    p_tab = p_tabs[i]
                    p_hash = get_attr(p_tab, "content_hash")
                    st = NodeChangeStatus.UNCHANGED if p_hash == c_tab.content_hash else NodeChangeStatus.CHANGED
                    matches.append(NodeMatch(
                        logical_key=c_tab.logical_key,
                        status=st,
                        prev_node_id=get_attr(p_tab, "id"),
                        curr_node_id=c_tab.id,
                        prev_hash=p_hash,
                        curr_hash=c_tab.content_hash,
                        node_type="table",
                        title_or_text=c_tab.title_or_text,
                        details="Table structure matched under parent"
                    ))
                    matched_prev_ids.add(get_attr(p_tab, "id"))
                    matched_curr_ids.add(c_tab.id)
                else:
                    matches.append(NodeMatch(
                        logical_key=c_tab.logical_key,
                        status=NodeChangeStatus.ADDED,
                        prev_node_id=None,
                        curr_node_id=c_tab.id,
                        prev_hash=None,
                        curr_hash=c_tab.content_hash,
                        node_type="table",
                        title_or_text=c_tab.title_or_text,
                        details="New table added under parent"
                    ))
                    matched_curr_ids.add(c_tab.id)

            # 3b. Lists
            p_lists = [c for c in p_content if get_attr(c, "node_type") == "list"]
            c_lists = [c for c in c_content if c.node_type.value == "list"]
            for i, c_list in enumerate(c_lists):
                if i < len(p_lists):
                    p_list = p_lists[i]
                    p_hash = get_attr(p_list, "content_hash")
                    st = NodeChangeStatus.UNCHANGED if p_hash == c_list.content_hash else NodeChangeStatus.CHANGED
                    matches.append(NodeMatch(
                        logical_key=c_list.logical_key,
                        status=st,
                        prev_node_id=get_attr(p_list, "id"),
                        curr_node_id=c_list.id,
                        prev_hash=p_hash,
                        curr_hash=c_list.content_hash,
                        node_type="list",
                        title_or_text=c_list.title_or_text,
                        details="List matched under parent"
                    ))
                    matched_prev_ids.add(get_attr(p_list, "id"))
                    matched_curr_ids.add(c_list.id)
                else:
                    matches.append(NodeMatch(
                        logical_key=c_list.logical_key,
                        status=NodeChangeStatus.ADDED,
                        prev_node_id=None,
                        curr_node_id=c_list.id,
                        prev_hash=None,
                        curr_hash=c_list.content_hash,
                        node_type="list",
                        title_or_text=c_list.title_or_text,
                        details="New list added under parent"
                    ))
                    matched_curr_ids.add(c_list.id)

            # 3c. Paragraphs
            p_paras = [c for c in p_content if get_attr(c, "node_type") == "paragraph"]
            c_paras = [c for c in c_content if c.node_type.value == "paragraph"]

            # First, match exact content hashes
            unmatched_p_paras = list(p_paras)
            unmatched_c_paras = []
            for cp in c_paras:
                found_match = None
                for pp in unmatched_p_paras:
                    if get_attr(pp, "content_hash") == cp.content_hash:
                        found_match = pp
                        break
                if found_match:
                    unmatched_p_paras.remove(found_match)
                    matches.append(NodeMatch(
                        logical_key=cp.logical_key,
                        status=NodeChangeStatus.UNCHANGED,
                        prev_node_id=get_attr(found_match, "id"),
                        curr_node_id=cp.id,
                        prev_hash=cp.content_hash,
                        curr_hash=cp.content_hash,
                        node_type="paragraph",
                        title_or_text=cp.title_or_text[:80],
                        details="Paragraph exact hash match"
                    ))
                    matched_prev_ids.add(get_attr(found_match, "id"))
                    matched_curr_ids.add(cp.id)
                else:
                    unmatched_c_paras.append(cp)

            # For remaining paragraphs under this parent, match by position index
            # This preserves logical identity when body text is modified!
            for i, cp in enumerate(unmatched_c_paras):
                if i < len(unmatched_p_paras):
                    pp = unmatched_p_paras[i]
                    p_hash = get_attr(pp, "content_hash")
                    matches.append(NodeMatch(
                        logical_key=cp.logical_key,
                        status=NodeChangeStatus.CHANGED,
                        prev_node_id=get_attr(pp, "id"),
                        curr_node_id=cp.id,
                        prev_hash=p_hash,
                        curr_hash=cp.content_hash,
                        node_type="paragraph",
                        title_or_text=cp.title_or_text[:80],
                        details="Paragraph modified under parent"
                    ))
                    matched_prev_ids.add(get_attr(pp, "id"))
                    matched_curr_ids.add(cp.id)
                else:
                    matches.append(NodeMatch(
                        logical_key=cp.logical_key,
                        status=NodeChangeStatus.ADDED,
                        prev_node_id=None,
                        curr_node_id=cp.id,
                        prev_hash=None,
                        curr_hash=cp.content_hash,
                        node_type="paragraph",
                        title_or_text=cp.title_or_text[:80],
                        details="New paragraph added under parent"
                    ))
                    matched_curr_ids.add(cp.id)

        # 4. Handle Content Nodes in Added Sections
        for cid, cn in curr_nodes.items():
            if cid not in matched_curr_ids:
                matches.append(NodeMatch(
                    logical_key=cn.logical_key,
                    status=NodeChangeStatus.ADDED,
                    prev_node_id=None,
                    curr_node_id=cn.id,
                    prev_hash=None,
                    curr_hash=cn.content_hash,
                    node_type=cn.node_type.value if hasattr(cn.node_type, "value") else str(cn.node_type),
                    title_or_text=cn.title_or_text[:80],
                    details="New node in added branch"
                ))
                matched_curr_ids.add(cid)

        # 5. Handle Removed Nodes from previous version
        for pid, pn in prev_nodes.items():
            if pid not in matched_prev_ids:
                matches.append(NodeMatch(
                    logical_key=get_attr(pn, "logical_key") or str(pid),
                    status=NodeChangeStatus.REMOVED,
                    prev_node_id=pid,
                    curr_node_id=None,
                    prev_hash=get_attr(pn, "content_hash"),
                    curr_hash=None,
                    node_type=get_attr(pn, "node_type", "unknown"),
                    title_or_text=(get_attr(pn, "title_or_text") or "")[:80],
                    details="Node removed in current version"
                ))
                matched_prev_ids.add(pid)


        # Summarize counts
        counts = {
            "added": sum(1 for m in matches if m.status == NodeChangeStatus.ADDED),
            "removed": sum(1 for m in matches if m.status == NodeChangeStatus.REMOVED),
            "changed": sum(1 for m in matches if m.status == NodeChangeStatus.CHANGED),
            "unchanged": sum(1 for m in matches if m.status == NodeChangeStatus.UNCHANGED),
            "ambiguous": sum(1 for m in matches if m.status == NodeChangeStatus.AMBIGUOUS),
        }

        return matches, counts
