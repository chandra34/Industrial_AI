"""
Unit tests for OPC UA Tag Catalog model, crawler, indexer, and tools.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.models import Base, OPCUATagCatalog
from backend.connectors.opcua.indexer import search_local_tag_catalog, get_catalog_status
from backend.utils.guardrails import check_tool_allowed


@pytest.mark.asyncio
async def test_opcua_tag_catalog_db_model():
    """Verify OPCUATagCatalog model creation and basic DB operations."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        tag = OPCUATagCatalog(
            node_id="ns=2;s=Line1.Pump01.Temp",
            browse_name="Temperature",
            display_name="Line 1 Pump 01 Temperature",
            full_path="Objects > Line_1 > Pump_01 > Temperature",
            node_class="Variable",
            unit="°C",
        )
        session.add(tag)
        await session.commit()

        result = await session.execute(select(OPCUATagCatalog))
        tags = result.scalars().all()
        assert len(tags) == 1
        assert tags[0].node_id == "ns=2;s=Line1.Pump01.Temp"
        assert tags[0].browse_name == "Temperature"

    await engine.dispose()


@pytest.mark.asyncio
async def test_search_local_tag_catalog():
    """Verify search_local_tag_catalog keyword matching accuracy."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        session.add_all([
            OPCUATagCatalog(
                node_id="ns=2;s=Line1.Pump01.Temp",
                browse_name="Temperature",
                display_name="Line 1 Pump 01 Temperature",
                full_path="Objects > Line_1 > Pump_01 > Temperature",
                node_class="Variable",
            ),
            OPCUATagCatalog(
                node_id="ns=2;s=Line1.Pump01.Press",
                browse_name="Pressure",
                display_name="Line 1 Pump 01 Pressure",
                full_path="Objects > Line_1 > Pump_01 > Pressure",
                node_class="Variable",
            ),
            OPCUATagCatalog(
                node_id="ns=2;s=Line2.Boiler.Temp",
                browse_name="Temperature",
                display_name="Line 2 Boiler Temperature",
                full_path="Objects > Line_2 > Boiler > Temperature",
                node_class="Variable",
            ),
        ])
        await session.commit()

        # Test search matching "pump"
        pump_results = await search_local_tag_catalog(session, "pump")
        assert len(pump_results) == 2

        # Test search matching "pump temperature"
        temp_results = await search_local_tag_catalog(session, "pump temperature")
        assert len(temp_results) == 1
        assert temp_results[0]["node_id"] == "ns=2;s=Line1.Pump01.Temp"

        # Test catalog status
        status = await get_catalog_status(session)
        assert status["total_tags"] == 3
        assert status["last_updated"] is not None

    await engine.dispose()


def test_guardrails_read_machine_telemetry():
    """Verify read_machine_telemetry and new IEC 62541 tools are whitelisted in guardrails."""
    assert check_tool_allowed("read_machine_telemetry") is True
    assert check_tool_allowed("search_opcua_nodes") is True
    assert check_tool_allowed("read_opcua_node_history") is True
    assert check_tool_allowed("get_opcua_alarm_events") is True


@pytest.mark.asyncio
async def test_opcua_history_and_alarm_tools_mock():
    """Verify read_opcua_node_history and get_opcua_alarm_events tool signatures."""
    from backend.agents.tools_registry import read_opcua_node_history, get_opcua_alarm_events

    history_res = await read_opcua_node_history(node_id="ns=3;i=1003")
    assert history_res["node_id"] == "ns=3;i=1003"
    assert "history" in history_res
    assert history_res["record_count"] >= 1

    alarm_res = await get_opcua_alarm_events(machine_node_id="ns=3;s=85/0:Simulation")
    assert alarm_res["machine_node_id"] == "ns=3;s=85/0:Simulation"
    assert "events" in alarm_res
    assert alarm_res["event_count"] >= 1

