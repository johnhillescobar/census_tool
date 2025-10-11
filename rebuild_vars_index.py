"""
Rebuild variable-level index with only acs/acs5 (to match table index)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from index.build_index import CensusIndexBuilder
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Build with ONLY acs/acs5 for Phase 8 consistency
builder = CensusIndexBuilder()

# Override to use only Detail Tables (acs/acs5)
datasets_phase8 = [
    ("acs/acs5", list(range(2012, 2024))),  # Only Detail Tables for Phase 8
]

logger.info("Rebuilding variable index with acs/acs5 only (Phase 8)")
builder.build_index(datasets=datasets_phase8)

logger.info("Variable index rebuild complete!")

