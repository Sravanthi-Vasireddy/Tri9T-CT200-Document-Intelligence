import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger("doc_intelligence.llm")


class LLMProviderError(Exception):
    """Safe exception raised on LLM provider errors without leaking secrets."""
    pass


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generates raw response text given system and user prompts."""
        pass


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    HTTP client for OpenAI and OpenAI-compatible providers (OpenRouter, Groq, Ollama, etc.).
    Uses httpx with structured JSON response format. Never exposes API key in logs or exceptions.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self._api_key = api_key or os.getenv("LLM_API_KEY", "")
        self._base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self._model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not self._api_key:
            logger.warning("LLM_API_KEY is not set. API calls will fail unless using a local unauthenticated endpoint.")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key and not ("localhost" in self._base_url or "127.0.0.1" in self._base_url):
            raise LLMProviderError("LLM API key is not configured. Set LLM_API_KEY environment variable.")

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            safe_msg = f"LLM provider returned HTTP {status_code}"
            logger.error(f"{safe_msg}: {e.response.text[:200]}")
            raise LLMProviderError(f"{safe_msg}. Please check your model configuration and quotas.")
        except httpx.TimeoutException:
            logger.error("LLM request timed out after 60s")
            raise LLMProviderError("LLM request timed out. Please try again.")
        except Exception as e:
            logger.error(f"Unexpected error calling LLM provider: {type(e).__name__}")
            raise LLMProviderError(f"Failed to communicate with LLM provider ({type(e).__name__}).")


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic, offline Mock LLM provider for rapid, reproducible testing.
    Inspects input nodes and produces strictly grounded CT-200 QA test cases
    using exact values from the provided document context.
    """

    def __init__(self, model: str = "mock-ct200-qa-v1"):
        self._model = model
        self.simulation_mode: Optional[str] = None  # Used by tests: 'malformed_json', 'invalid_count', 'unknown_node'

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Check simulation modes for testing error & repair paths
        if self.simulation_mode == "malformed_json":
            self.simulation_mode = None  # Reset after 1st attempt to test repair
            return "{ 'test_cases': [ invalid json without closing bracket"

        if self.simulation_mode == "invalid_count":
            self.simulation_mode = None
            return json.dumps({
                "test_cases": [
                    {
                        "id": "TC-CT200-001",
                        "title": "Solo Test",
                        "objective": "Verify behavior",
                        "preconditions": ["Device ready"],
                        "test_steps": ["Step 1"],
                        "expected_result": "Expected result",
                        "priority": "high",
                        "source_node_ids": ["v1_sec_1"],
                        "requirement_coverage": "Coverage"
                    }
                ]
            })

        # Parse available source node IDs from prompt
        node_ids_match = re.search(r"AVAILABLE SOURCE NODE IDS.*?\:\s*([^\n]+)", user_prompt)
        available_node_ids = []
        if node_ids_match:
            available_node_ids = [nid.strip() for nid in node_ids_match.group(1).split(",") if nid.strip()]

        primary_id = available_node_ids[0] if available_node_ids else "v1_doc_root"
        secondary_id = available_node_ids[1] if len(available_node_ids) > 1 else primary_id

        # Detect specific content in prompt
        is_v1_battery = "300 measurement cycles" in user_prompt
        is_v2_battery = "250 measurement cycles" in user_prompt
        has_table = "Pressure Measurement Range" in user_prompt or "Error Code" in user_prompt
        has_shutoff = "Auto Shutoff" in user_prompt or "1 minute" in user_prompt

        test_cases = []

        # Test Case 1: Battery / Operating Life Verification
        if is_v1_battery:
            test_cases.append({
                "id": "TC-CT200-BAT-001",
                "title": "V1 Typical Battery Life and Low-Battery Threshold Verification",
                "objective": "Verify that typical battery life delivers approximately 300 measurement cycles and triggers low-battery indicator below 15%.",
                "preconditions": [
                    "CardioTrack CT-200 unit installed with fresh AAA alkaline batteries",
                    "Simulated measurement rig connected to verify cycle count"
                ],
                "test_steps": [
                    "Execute consecutive simulated measurement cycles (3 per day equivalent).",
                    "Monitor battery voltage degradation until 300 cycles are reached.",
                    "Discharge battery cell voltage to 15% remaining capacity."
                ],
                "expected_result": "The device completes 300 measurement cycles under normal load, and low-battery warning icon appears exactly when capacity drops below 15%.",
                "priority": "high",
                "source_node_ids": [primary_id],
                "requirement_coverage": "Section 2.1.1.1 (Battery Life Under Typical Use - V1)",
                "ambiguities_or_flags": None
            })
        elif is_v2_battery:
            test_cases.append({
                "id": "TC-CT200-BAT-002",
                "title": "V2 Revised Battery Life and Low-Battery Threshold Verification",
                "objective": "Verify that typical battery life delivers approximately 250 measurement cycles and triggers low-battery indicator below 10%.",
                "preconditions": [
                    "CardioTrack CT-200 unit (V2 firmware) installed with standard batteries",
                    "Battery test station calibrated"
                ],
                "test_steps": [
                    "Run automated measurement cycles under nominal temperature (+10°C to +40°C).",
                    "Record total successful cycles before low-battery cutoff.",
                    "Drop supply voltage to 10% remaining capacity."
                ],
                "expected_result": "Device supports 250 measurement cycles, and low-battery icon illuminates when battery drops below 10%.",
                "priority": "high",
                "source_node_ids": [primary_id],
                "requirement_coverage": "Section 2.1.1.1 (Battery Life Under Typical Use - V2)",
                "ambiguities_or_flags": None
            })
        else:
            test_cases.append({
                "id": "TC-CT200-GEN-001",
                "title": "Primary Operational Sequence and Device Readiness",
                "objective": "Verify initial device initialization and readiness sequence as specified in requirements.",
                "preconditions": [
                    "Device powered on within operating conditions (+10°C to +40°C, 15% to 85% RH)"
                ],
                "test_steps": [
                    "Power on the device by pressing the Start/Stop button.",
                    "Observe display segments during self-test."
                ],
                "expected_result": "Display activates all LCD segments and transitions to ready state without error indicators.",
                "priority": "high",
                "source_node_ids": [primary_id],
                "requirement_coverage": "Operational readiness verification",
                "ambiguities_or_flags": None
            })

        # Test Case 2: Measurement Range & Accuracy
        if "0 to 299 mmHg" in user_prompt or has_table:
            test_cases.append({
                "id": "TC-CT200-SPEC-002",
                "title": "Pressure Measurement Boundary and Accuracy Verification",
                "objective": "Verify device measurement across 0 to 299 mmHg range with ±3 mmHg pressure accuracy.",
                "preconditions": [
                    "Calibrated mercury manometer or digital pressure standard attached in parallel",
                    "Rigid calibration cylinder cuff chamber"
                ],
                "test_steps": [
                    "Apply test pressures at lower boundary (20 mmHg), midpoint (120 mmHg), and upper boundary (280 mmHg).",
                    "Compare device LCD reading against calibrated reference standard."
                ],
                "expected_result": "Measured pressure matches reference standard within ±3 mmHg across the entire 0 to 299 mmHg range.",
                "priority": "critical",
                "source_node_ids": [secondary_id],
                "requirement_coverage": "Section 2.1 General Specifications table",
                "ambiguities_or_flags": None
            })
        else:
            test_cases.append({
                "id": "TC-CT200-OPR-002",
                "title": "Cuff Inflation Sequence Verification",
                "objective": "Verify micro rolling pump automatic inflation sequence during measurement cycle.",
                "preconditions": [
                    "Arm cuff properly fitted to standard adult arm simulator (22–42 cm)"
                ],
                "test_steps": [
                    "Press START button to initiate measurement.",
                    "Verify automatic pump activation and continuous pressure ramp."
                ],
                "expected_result": "Pump inflates cuff smoothly without sudden deceleration or pressure stuttering.",
                "priority": "medium",
                "source_node_ids": [secondary_id],
                "requirement_coverage": "Section 3 Operating Instructions",
                "ambiguities_or_flags": None
            })

        # Test Case 3: Safety / Auto Shutoff / Error Handling
        if has_shutoff:
            test_cases.append({
                "id": "TC-CT200-SFT-003",
                "title": "Automatic Power Shutoff After Inactivity",
                "objective": "Verify device automatically powers off after exactly 1 minute of inactivity.",
                "preconditions": [
                    "Device in idle state displaying final measurement reading",
                    "No buttons pressed"
                ],
                "test_steps": [
                    "Complete a measurement cycle.",
                    "Leave device untouched and start precision digital timer.",
                    "Record time elapsed when LCD screen turns off."
                ],
                "expected_result": "Device screen completely powers off after exactly 1 minute (60 seconds) of inactivity.",
                "priority": "medium",
                "source_node_ids": [primary_id],
                "requirement_coverage": "Section 3.4 Auto Shutoff",
                "ambiguities_or_flags": None
            })
        else:
            test_cases.append({
                "id": "TC-CT200-SFT-003",
                "title": "Safety Overpressure Protection and Deflation Response",
                "objective": "Verify rapid automatic pressure venting upon detection of overpressure condition.",
                "preconditions": [
                    "Cuff pneumatic simulator configured with high-pressure transient generator"
                ],
                "test_steps": [
                    "Force system pneumatic pressure above upper threshold.",
                    "Measure deflation valve release response time."
                ],
                "expected_result": "Electronic control valve vents pressure rapidly to protect patient safety.",
                "priority": "critical",
                "source_node_ids": [primary_id],
                "requirement_coverage": "Pressure safety specification",
                "ambiguities_or_flags": None
            })

        return json.dumps({"test_cases": test_cases})


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """Factory creating configured LLM provider instance."""
    p_name = (provider_name or os.getenv("LLM_PROVIDER", "mock")).strip().lower()

    if p_name == "openai":
        return OpenAICompatibleProvider()
    elif p_name == "mock":
        return MockLLMProvider()
    else:
        logger.warning(f"Unknown LLM provider '{p_name}'. Falling back to MockLLMProvider.")
        return MockLLMProvider()
