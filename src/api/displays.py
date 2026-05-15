"""CLI display surface — consumes typed ``CensusState`` only (Track 2C)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.domain.rendered_output_contract import RenderedArtifactFailure, RenderedArtifactSuccess
from src.state.types import CensusState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def census_state_from_graph_invoke(payload: Mapping[str, Any] | CensusState) -> CensusState:
    """
    Single adapter from a LangGraph invoke result (mapping) to ``CensusState``.

    Use this at CLI (or other) boundaries; keep ``display_results`` strictly typed.
    """
    if isinstance(payload, CensusState):
        return payload
    return CensusState.model_validate(dict(payload))


def display_results(state: CensusState) -> None:
    """Display the results of the Census query from workflow state."""

    print("\n" + "=" * 50)
    print("CENSUS DATA RESULTS")
    print("=" * 50)

    if state.error:
        print(f"\n[ERROR] Error: {state.error}")
        return

    final = state.final
    if not final:
        print("\n[ERROR] No answer available")
        return

    if final.answer_text:
        print(f"\n[ANSWER] {final.answer_text}")

    generated_files = final.generated_files if final.generated_files else []
    if generated_files:
        print(f"\n[FILES GENERATED]: {len(generated_files)} artifact(s)")
        for i, artifact in enumerate(generated_files, 1):
            if isinstance(artifact, RenderedArtifactFailure):
                label = artifact.title or artifact.kind
                print(
                    f"  {i}. [RENDER FAILED] {artifact.kind} "
                    f"({artifact.error_code}) {label}: {artifact.message}"
                )
            elif isinstance(artifact, RenderedArtifactSuccess):
                t = artifact.title or Path(artifact.path).name
                print(
                    f"  {i}. {artifact.kind.upper()} path={artifact.path} "
                    f"mime={artifact.mime_type} title={t}"
                )
            else:
                print(f"  {i}. {artifact}")

    if final.charts_needed:
        print(f"\n[CHARTS REQUESTED]: {len(final.charts_needed)} chart(s)")
        for chart in final.charts_needed:
            print(f"  - {chart.type.title()} chart: {chart.title or 'Untitled'}")

    if final.tables_needed:
        print(f"\n[TABLES REQUESTED]: {len(final.tables_needed)} table(s)")
        for table in final.tables_needed:
            print(f"  - {table.format.upper()} table: {table.filename or 'untitled'}")

    if final.footnotes:
        print("\n📝 Footnotes:")
        logger.info("Footnotes: %s", final.footnotes)
        for i, footnote in enumerate(final.footnotes):
            print(f"  {i + 1}. {footnote}")

    logs = state.logs or []
    if logs:
        print(f"\n System Logs: {len(logs)} entries")
        logger.info("System Logs: %s", logs)
        for log in logs[-3:]:
            print(f"  • {log}")
