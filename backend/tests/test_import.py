"""Service-level coverage for CSV episode import behaviour."""

from io import StringIO

import pytest
from app.models.episode import Episode
from app.services.episode_import_service import EpisodeImportService
from sqlalchemy import select

CSV_HEADER = (
    "episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality"
)


def csv_document(*rows: str) -> StringIO:
    return StringIO("\n".join((CSV_HEADER, *rows)))


@pytest.mark.asyncio
async def test_import_inserts_valid_rows_and_reports_invalid_ones(db_session):
    summary = await EpisodeImportService(db_session).import_csv(
        csv_document(
            "EP-001,arm-01,pick_cups,2026-01-10T09:00:00Z,42.5,Ada,good",
            "EP-002,arm-02,pick_cups,not-a-date,42.5,Ben,good",
            "EP-003,arm-03,pick_cups,2026-01-10T09:00:00Z,-1,Cam,good",
        )
    )

    episodes = (await db_session.execute(select(Episode))).scalars().all()
    assert summary.imported == 1
    assert summary.skipped_duplicates == 0
    assert summary.invalid == 2
    assert [error.row for error in summary.errors] == [3, 4]
    assert "recorded_at" in summary.errors[0].reason
    assert "duration_seconds" in summary.errors[1].reason
    assert [episode.episode_id for episode in episodes] == ["EP-001"]


@pytest.mark.asyncio
async def test_import_reports_duplicates_as_skipped_and_is_idempotent(db_session):
    document = csv_document(
        "EP-010,arm-01,pick_cups,2026-01-10T09:00:00Z,42,Ada,good",
        "EP-011,arm-02,pick_cups,2026-01-10T10:00:00Z,43,Ben,usable",
    )
    service = EpisodeImportService(db_session)

    first = await service.import_csv(document)
    second = await service.import_csv(
        csv_document(
            "EP-010,arm-01,pick_cups,2026-01-10T09:00:00Z,42,Ada,good",
            "EP-011,arm-02,pick_cups,2026-01-10T10:00:00Z,43,Ben,usable",
        )
    )

    episodes = (await db_session.execute(select(Episode))).scalars().all()
    assert first.imported == 2
    assert first.skipped_duplicates == 0
    assert second.imported == 0
    assert second.skipped_duplicates == 2
    assert second.invalid == 0
    assert len(episodes) == 2


@pytest.mark.asyncio
async def test_import_caps_retained_errors_but_counts_all_invalid_rows(db_session):
    rows = [
        f"EP-{index:03d},arm-01,pick_cups,2026-01-10T09:00:00Z,0,Ada,good"
        for index in range(101)
    ]

    summary = await EpisodeImportService(db_session).import_csv(csv_document(*rows))

    assert summary.imported == 0
    assert summary.invalid == 101
    assert len(summary.errors) == 100
    assert summary.errors_truncated is True
