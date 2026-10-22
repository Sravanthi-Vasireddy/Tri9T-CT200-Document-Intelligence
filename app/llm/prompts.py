from typing import List, Dict, Any, Optional

PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are a Principal Medical Device QA Engineering Assistant specialized in the CardioTrack CT-200 Blood Pressure Monitor documentation.
Your goal is to generate 3 to 5 rigorous, concrete, actionable, and verifiable QA test cases strictly grounded in the supplied technical requirements.

MANDATORY RULES:
1. OUTPUT FORMAT: You MUST return ONLY a valid JSON object matching the requested schema. Do not enclose the output in Markdown backticks (e.g. ```json ... ```) or include introductory or concluding conversational prose.
2. QUANTITY: Generate strictly between 3 and 5 distinct test cases (3 <= count <= 5). Never duplicate test objectives or steps.
3. GROUNDING: Every precondition, step, and expected result MUST be directly substantiated by the provided requirements text. NEVER invent device specifications, operating thresholds, clinical classifications, or safety behaviors absent from the text.
4. NUMERICAL & LOGICAL FIDELITY: Preserve all numerical values (e.g. 300 cycles, 250 cycles, 0 to 299 mmHg, 40 to 180 beats/min, 15%, 10%), units, mathematical inequalities (<, >, <=, >=), and negations ("cannot be silenced", "shall not inflate") exactly as stated.
5. SOURCE TRACEABILITY: Each test case MUST cite the exact version-specific source_node_ids supporting it from the provided list of Available Node IDs. Never invent or cite node IDs outside this provided list.
6. ACTIONABLE & VERIFIABLE: Test steps must specify concrete tester actions, inputs, or environmental setups. The expected result must be measurable and verifiable.
7. AMBIGUITY HANDLING: If a requirement is underspecified, contradictory, or ambiguous in the source text, explicitly flag the ambiguity in the "ambiguities_or_flags" field instead of assuming or fabricating a behavior.
8. PRIORITIES: Set priority to one of: "critical", "high", "medium", or "low".
"""

USER_PROMPT_TEMPLATE = """DOCUMENT CONTEXT:
Document ID: {document_id}
Pinned Version: {version_number}
Selection Name: {selection_name}
{additional_instructions_section}

SOURCE REQUIREMENTS NODES:
{nodes_context}

AVAILABLE SOURCE NODE IDS (You must ONLY cite from this list):
{valid_node_ids_str}

REQUIRED JSON SCHEMA:
{{
  "test_cases": [
    {{
      "id": "TC-CT200-001",
      "title": "<Concise descriptive title>",
      "objective": "<Specific device requirement or boundary being verified>",
      "preconditions": [
        "<Precondition 1>",
        "<Precondition 2>"
      ],
      "test_steps": [
        "Step 1: ...",
        "Step 2: ..."
      ],
      "expected_result": "<Measurable, verifiable outcome with exact values from text>",
      "priority": "critical | high | medium | low",
      "source_node_ids": ["<valid_node_id_from_above_list>"],
      "requirement_coverage": "<Brief rationale linking steps to source requirement>",
      "ambiguities_or_flags": null or "<Description of any underspecified requirement>"
    }}
  ]
}}
"""

REPAIR_PROMPT_TEMPLATE = """Your previous response failed validation with the following errors:
{validation_errors}

PREVIOUS RESPONSE:
{previous_raw_output}

INSTRUCTION:
Fix all identified schema and validation errors. Ensure that:
1. Output is valid, parseable JSON matching the schema.
2. The count of test cases is strictly between 3 and 5.
3. Every test case contains non-empty title, objective, test_steps, expected_result, and priority (critical, high, medium, low).
4. source_node_ids ONLY contains valid IDs from this list:
{valid_node_ids_str}

Output ONLY the corrected JSON object now.
"""


def format_nodes_context(nodes: List[Dict[str, Any]]) -> str:
    """Formats node context for injection into LLM prompts."""
    formatted_chunks = []
    for node in nodes:
        header = f"--- [Node ID: {node['node_id']}] [Key: {node.get('logical_key', '')}] [Type: {node.get('node_type', '')}] ---"
        if node.get("section_number"):
            header += f" [Section: {node['section_number']}]"
        body = node.get("title_or_text", "").strip()
        table_data = node.get("table_data")
        if table_data and isinstance(table_data, dict):
            headers = " | ".join(table_data.get("headers", []))
            rows_str = "\n".join([" | ".join(str(cell or "") for cell in row) for row in table_data.get("rows", [])])
            body += f"\nTable Data:\n| {headers} |\n{rows_str}"
        formatted_chunks.append(f"{header}\n{body}\n")
    return "\n".join(formatted_chunks)


def build_user_prompt(
    document_id: str,
    version_number: str,
    selection_name: str,
    nodes: List[Dict[str, Any]],
    valid_node_ids: List[str],
    additional_instructions: Optional[str] = None
) -> str:
    """Builds the complete grounded user prompt."""
    nodes_context = format_nodes_context(nodes)
    valid_node_ids_str = ", ".join(valid_node_ids)
    add_section = f"Additional QA Focus: {additional_instructions}\n" if additional_instructions else ""

    return USER_PROMPT_TEMPLATE.format(
        document_id=document_id,
        version_number=version_number,
        selection_name=selection_name,
        additional_instructions_section=add_section,
        nodes_context=nodes_context,
        valid_node_ids_str=valid_node_ids_str
    )


def build_repair_prompt(
    validation_errors: str,
    previous_raw_output: str,
    valid_node_ids: List[str]
) -> str:
    """Builds prompt for single-attempt repair on validation failure."""
    return REPAIR_PROMPT_TEMPLATE.format(
        validation_errors=validation_errors,
        previous_raw_output=previous_raw_output,
        valid_node_ids_str=", ".join(valid_node_ids)
    )
