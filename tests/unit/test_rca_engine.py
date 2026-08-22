"""
Unit tests for the Event-Driven Autonomous RCA Engine and Debouncer.
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.analytics.rca_engine import RCAEngine
from backend.agents.schemas import AgentResponse


class TestRCAEngineDebounce:
    def test_initial_trigger_not_debounced(self):
        engine = RCAEngine(debounce_seconds=900)
        assert engine.is_debounced("Pump_01::High_Temp") is False

    def test_repeated_trigger_is_debounced(self):
        engine = RCAEngine(debounce_seconds=900)
        key = "Pump_01::High_Temp"
        engine.mark_triggered(key)
        assert engine.is_debounced(key) is True

    def test_different_asset_not_debounced(self):
        engine = RCAEngine(debounce_seconds=900)
        engine.mark_triggered("Pump_01::High_Temp")
        assert engine.is_debounced("Boiler_02::High_Pressure") is False

    def test_debounce_expires_after_window(self):
        engine = RCAEngine(debounce_seconds=0.1)  # 100ms window for test
        key = "Compressor_03::Vibration"
        engine.mark_triggered(key)
        assert engine.is_debounced(key) is True
        time.sleep(0.15)
        assert engine.is_debounced(key) is False


class TestRCAPromptAndParsing:
    def test_build_rca_prompt_contains_all_pillars(self):
        engine = RCAEngine()
        prompt = engine.build_rca_prompt(
            asset_name="Boiler Feed Pump 02",
            node_id="ns=2;s=Line1.Pump02",
            alarm_type="High Vibration Trip (4.8 mm/s)",
            severity="CRITICAL",
        )
        assert "detect_telemetry_anomalies" in prompt
        assert "SAP PM HISTORY" in prompt
        assert "OEM MANUAL RAG" in prompt

    def test_parse_structured_rca_response(self):
        engine = RCAEngine()
        sample_response = (
            "PRIMARY ROOT CAUSE: Bearing lubrication failure due to grease starvation.\n"
            "CONFIDENCE SCORE: 92%\n"
            "TELEMETRY EVIDENCE: Vibration RMS in ISO Zone C (4.8 mm/s), Crest Factor 4.1.\n"
            "SAP MAINTENANCE EVIDENCE: Last greasing was 14 months ago in Notification #400192.\n"
            "OEM SOP CITATION: Section 4.2 of Equipment Maintenance Manual.\n"
            "RECOMMENDED ACTIONS:\n"
            "1. Perform Lockout/Tagout on Pump 02.\n"
            "2. Inspect bearing housing for metallic wear.\n"
            "3. Apply Mobil Polyrex EM lubricant.\n"
        )
        parsed = engine._parse_rca_response(sample_response)
        assert "grease starvation" in parsed["root_cause"].lower()
        assert parsed["confidence_score"] == 92
        assert len(parsed["recommended_actions"]) == 3
        assert "Lockout/Tagout" in parsed["recommended_actions"][0]

    @pytest.mark.asyncio
    async def test_execute_rca_saves_to_db(self):
        engine = RCAEngine(debounce_seconds=900)

        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock(return_value=AgentResponse(
            query="test query",
            answer="PRIMARY ROOT CAUSE: Overheating due to coolant blockage.\nCONFIDENCE SCORE: 88%\nRECOMMENDED ACTIONS:\n1. Check coolant valve.",
            steps_taken=2,
            tool_calls=[],
            llm_provider_used="gemini",
            llm_model_used="gemini-2.5-pro",
        ))

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        record = await engine.execute_rca(
            asset_name="Test Compressor",
            node_id="ns=2;s=Comp01",
            alarm_type="Overheating Trip",
            severity="CRITICAL",
            orchestrator=mock_orchestrator,
            db_session=mock_db,
            force=True,
        )

        assert record is not None
        assert record.asset_name == "Test Compressor"
        assert "coolant blockage" in record.root_cause.lower()
        assert record.confidence_score == 88
        assert mock_db.add.called
        assert mock_db.commit.called
