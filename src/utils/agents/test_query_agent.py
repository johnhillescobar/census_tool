import os
import sys
from dotenv import load_dotenv
from src.utils.agents.census_query_agent import CensusQueryAgent

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.insert(0, project_root)

load_dotenv()

# Create agent
agent = CensusQueryAgent()

# Test query
result = agent.solve(
    user_query="Compare population by county in California",
    intent={"topic": "population", "geography": "county", "state": "California"},
)
print("Agent Result:", result)
