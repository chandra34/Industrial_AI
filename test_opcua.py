import asyncio
import logging
from backend.connectors.opcua import OPCUAClient, OPCUAConfig
from backend.connectors.opcua.reader import OPCUAReader
from backend.connectors.opcua.browser import OPCUABrowser

# Enable logging output
logging.basicConfig(level=logging.INFO)

async def test_opcua():
    # Automatically loads OPCUA_ENDPOINT_URL from .env file
    config = OPCUAConfig()
    print(f"\n[0] Loaded config from .env -> Endpoint: {config.endpoint_url}")

    print("\n[1] Connecting to Prosys OPC UA Demo Server...")
    async with OPCUAClient(config) as client:
        print("[+] SUCCESS: Connected to Server!")

        # Test Browser
        print("\n[2] Browsing child nodes under Objects...")
        browser = OPCUABrowser(client)
        children = await browser.browse_children()
        print(f"[+] SUCCESS: Discovered {len(children)} child nodes.")

        # Test Reader with the exact NodeID from UaExpert
        node_id = "ns=3;i=1001"
        print(f"\n[3] Reading live tag value for NodeId '{node_id}' (Counter)...")
        reader = OPCUAReader(client)
        val = await reader.read_node_value(node_id)
        print(f"🎉 SUCCESS! Live Counter Value from OPC UA Server = {val}\n")

        # Detailed metadata read test
        details = await reader.read_node_details(node_id)
        print(f"[4] Detailed Tag Metadata: {details}\n")

if __name__ == "__main__":
    asyncio.run(test_opcua())
