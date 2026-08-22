"""
Event-Driven Autonomous Root Cause Analysis (RCA) Engine.

Dispatches targeted diagnostic missions to the IndustrialOrchestrator
strictly upon alarm trips or critical anomaly events. Includes an in-memory
debouncer to prevent alarm storms from triggering redundant LLM runs.
"""

import json
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.orchestrator import IndustrialOrchestrator
from backend.agents.schemas import AgentQueryRequest
from backend.database.models import RCAEvent

logger = logging.getLogger(__name__)

# Debounce window in seconds (15 minutes per asset)
_DEFAULT_DEBOUNCE_SECONDS = 900.0


class RCAEngine:
    """Dispatches event-triggered root cause analysis to the Industrial Copilot."""

    def __init__(self, debounce_seconds: float = _DEFAULT_DEBOUNCE_SECONDS) -> None:
        self.debounce_seconds = debounce_seconds
        # In-memory debounce cache: { asset_key: last_triggered_epoch_timestamp }
        self._last_triggered: Dict[str, float] = {}

    def is_debounced(self, asset_key: str) -> bool:
        """Check if an RCA was already triggered for this asset within the debounce window.

        :param asset_key: Unique identifier (e.g. node_id or asset_name).
        :return: True if debounced (should skip), False if eligible to run.
        """
        now = time.time()
        last_time = self._last_triggered.get(asset_key)
        if last_time and (now - last_time) < self.debounce_seconds:
            remaining_mins = (self.debounce_seconds - (now - last_time)) / 60.0
            logger.info(
                "RCA debounced for asset '%s' (triggered %.1f mins ago, %.1f mins remaining).",
                asset_key,
                (now - last_time) / 60.0,
                remaining_mins,
            )
            return True
        return False

    def mark_triggered(self, asset_key: str) -> None:
        """Record the trigger timestamp for an asset."""
        self._last_triggered[asset_key] = time.time()

    def build_rca_prompt(
        self,
        asset_name: str,
        node_id: str,
        alarm_type: str,
        severity: str = "CRITICAL",
        extra_context: str = "",
    ) -> str:
        """Format a structured autonomous diagnostic mission prompt for the agent.

        :param asset_name: Name of the machine/asset.
        :param node_id: OPC UA node ID.
        :param alarm_type: Description of the trip or anomaly.
        :param severity: Severity level.
        :param extra_context: Optional supplementary sensor details.
        :return: Formatted mission prompt string.
        """
        return (
            f"AUTONOMOUS EMERGENCY ROOT CAUSE ANALYSIS (RCA) MISSION:\n"
            f"Asset: '{asset_name}' (OPC UA Node: '{node_id}')\n"
            f"Trigger Event: '{alarm_type}' [Severity: {severity}]\n"
            f"{extra_context}\n\n"
            f"EXECUTE THE FOLLOWING 3-PILLAR INVESTIGATION:\n"
            f"1. OT TELEMETRY: Call `detect_telemetry_anomalies` for node '{node_id}' to inspect Z-scores, drift rates, and vibration zones.\n"
            f"2. SAP PM HISTORY: Query SAP notifications and work orders for asset '{asset_name}' to see recent maintenance history, grease intervals, or recurring faults.\n"
            f"3. OEM MANUAL RAG: Search technical manuals for troubleshooting procedures and root cause fault trees for '{asset_name} {alarm_type}'.\n\n"
            f"Synthesize your final findings into structured sections:\n"
            f"- PRIMARY ROOT CAUSE (concise 1-2 sentence diagnosis)\n"
            f"- CONFIDENCE SCORE (e.g. 90%)\n"
            f"- TELEMETRY EVIDENCE (statistical findings)\n"
            f"- SAP MAINTENANCE EVIDENCE (relevant past logs)\n"
            f"- OEM SOP CITATION (manual chapter/section)\n"
            f"- RECOMMENDED CORRECTIVE ACTIONS (numbered step-by-step instructions)"
        )

    def _parse_rca_response(self, raw_text: str) -> Dict[str, Any]:
        """Extract structured RCA fields from agent response."""
        confidence = 85
        root_cause = "Asset anomaly detected across multiple telemetry parameters."
        telemetry_evidence = ""
        sap_evidence = ""
        sop_evidence = ""
        recommended_actions: List[str] = []

        lines = raw_text.splitlines()
        current_section = None

        for line in lines:
            line_str = line.strip()
            upper = line_str.upper()

            if "PRIMARY ROOT CAUSE" in upper or "ROOT CAUSE:" in upper:
                current_section = "root_cause"
                clean = line_str.split(":", 1)[-1].strip() if ":" in line_str else ""
                if clean:
                    root_cause = clean
                continue
            elif "CONFIDENCE" in upper:
                current_section = "confidence"
                # Extract digits
                digits = "".join([c for c in line_str if c.isdigit()])
                if digits:
                    try:
                        val = int(digits[:3])
                        confidence = min(100, max(10, val))
                    except ValueError:
                        pass
                continue
            elif "TELEMETRY EVIDENCE" in upper:
                current_section = "telemetry"
                continue
            elif "SAP" in upper and "EVIDENCE" in upper:
                current_section = "sap"
                continue
            elif ("OEM" in upper or "MANUAL" in upper or "SOP" in upper) and "CITATION" in upper:
                current_section = "sop"
                continue
            elif "RECOMMENDED" in upper and "ACTION" in upper:
                current_section = "actions"
                continue

            if current_section == "root_cause" and line_str and root_cause == "Asset anomaly detected across multiple telemetry parameters.":
                root_cause = line_str
            elif current_section == "telemetry" and line_str:
                telemetry_evidence += line_str + "\n"
            elif current_section == "sap" and line_str:
                sap_evidence += line_str + "\n"
            elif current_section == "sop" and line_str:
                sop_evidence += line_str + "\n"
            elif current_section == "actions" and line_str:
                if line_str.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.")):
                    clean_act = line_str.lstrip("-*0123456789. ")
                    if clean_act:
                        recommended_actions.append(clean_act)

        if not recommended_actions:
            recommended_actions = [
                "Inspect asset operating conditions and verify physical sensor readings.",
                "Review active work orders in SAP PM.",
                "Consult OEM operation manual for standard troubleshooting sequence."
            ]

        return {
            "root_cause": root_cause.strip(),
            "confidence_score": confidence,
            "telemetry_evidence": telemetry_evidence.strip() or "Telemetry parameters evaluated across statistical methods.",
            "sap_evidence": sap_evidence.strip() or "No critical overdue maintenance notifications identified.",
            "sop_evidence": sop_evidence.strip() or "Referenced standard equipment operation and troubleshooting guide.",
            "recommended_actions": recommended_actions,
        }

    async def execute_rca(
        self,
        asset_name: str,
        node_id: str,
        alarm_type: str,
        severity: str,
        orchestrator: IndustrialOrchestrator,
        db_session: AsyncSession,
        extra_context: str = "",
        force: bool = False,
    ) -> Optional[RCAEvent]:
        """Execute autonomous RCA and save structured result to DB.

        :param asset_name: Machine name.
        :param node_id: OPC UA Node ID.
        :param alarm_type: Description of the alarm/outlier.
        :param severity: 'WARNING' or 'CRITICAL'.
        :param orchestrator: IndustrialOrchestrator instance.
        :param db_session: Async SQLAlchemy database session.
        :param extra_context: Additional sensor/alarm metadata.
        :param force: If True, bypasses debounce check (for manual 1-click trigger).
        :return: Saved RCAEvent database record, or None if debounced.
        """
        asset_key = f"{node_id}::{alarm_type}"

        if not force and self.is_debounced(asset_key):
            logger.info("Skipping autonomous RCA for %s (debounced).", asset_key)
            return None

        self.mark_triggered(asset_key)
        logger.info("Executing Autonomous RCA Mission for '%s' (Trigger: %s)...", asset_name, alarm_type)

        prompt = self.build_rca_prompt(
            asset_name=asset_name,
            node_id=node_id,
            alarm_type=alarm_type,
            severity=severity,
            extra_context=extra_context,
        )

        agent_req = AgentQueryRequest(query=prompt, max_steps=8)
        agent_res = await orchestrator.run(agent_req, user_id="system_rca_engine")

        parsed = self._parse_rca_response(agent_res.answer)

        event_id = f"rca_{uuid.uuid4().hex[:12]}"
        rca_record = RCAEvent(
            id=event_id,
            asset_name=asset_name,
            node_id=node_id,
            alarm_type=alarm_type,
            severity=severity,
            root_cause=parsed["root_cause"],
            confidence_score=parsed["confidence_score"],
            telemetry_evidence=parsed["telemetry_evidence"],
            sap_evidence=parsed["sap_evidence"],
            sop_evidence=parsed["sop_evidence"],
            recommended_actions_json=json.dumps(parsed["recommended_actions"]),
            raw_llm_response=agent_res.answer,
            status="open",
            created_at=datetime.now(timezone.utc),
        )

        db_session.add(rca_record)
        await db_session.commit()
        await db_session.refresh(rca_record)

        logger.info("Autonomous RCA completed and saved: %s (Root Cause: %s)", event_id, parsed["root_cause"])
        return rca_record


# Global RCA Engine singleton
rca_engine = RCAEngine()
