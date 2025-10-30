from src.tools.area_resolution_tool import AreaResolutionTool
from src.tools.geography_discovery_tool import GeographyDiscoveryTool
import json

# Test AreaResolutionTool
print("Testing AreaResolutionTool...")
tool = AreaResolutionTool()
result = tool.run(json.dumps({"name": "California", "geography_type": "state"}))
print(f"Result: {result}")

# Test GeographyDiscoveryTool
print("\nTesting GeographyDiscoveryTool...")
geo_tool = GeographyDiscoveryTool()
result2 = geo_tool.run(json.dumps({"action": "enumerate_areas", "level": "state"}))
print(f"Result: {result2[:200]}...")  # First 200 chars
