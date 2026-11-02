"""Offline correction of replaceable historical market repetition."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, replace
from hashlib import sha256
from unittest.mock import patch

import pytest

from app.bootstrap import build_market_stock_repair
from app.domain.contracts import ContractOffer
from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate, StockPolicy
from app.domain.market_stock_repair import (
    MarketStockRepairContext,
    RepairableMarketOffer,
)
from app.repositories.database_backup import backup_database
from app.repositories.market_stock_repair import SqliteMarketStockRepairStore
from app.services.market.selection import MarketSelectionService
from app.services.market.stock.maintenance import (
    MarketStockRepairPlanner,
    MarketStockRepairService,
)


class MemoryMarketStockRepairStore:
    """Expose explicit contexts behind the production maintenance port."""

    def __init__(self, contexts):
        self._contexts = contexts

    def contexts(self):
        return self._contexts

    def repair_to(self, plan, target, archive, now):
        """Reject writes from the inspection-only test double."""
        del plan, target, archive, now
        raise AssertionError("Inspection test must not write repair output")


def _repair_context(diverse_stock_game):
    """Build one full repetitive band with two prepared alternatives."""
    game, _, batch = diverse_stock_game
    snapshot = batch.snapshots.read()
    candidates = []
    signatures = set()
    band = snapshot.candidates[0].distance_profile.distance_band
    for candidate in snapshot.candidates:
        if candidate.distance_profile.distance_band != band:
            continue
        signature = (
            candidate.trade.origin.facility_uid,
            candidate.trade.destination.facility_uid,
            candidate.trade.cargo.nhm_row_id,
        )
        if signature not in signatures:
            signatures.add(signature)
            candidates.append(candidate)
        if len(candidates) == 3:
            break
    assert len(candidates) == 3
    factory = game.market_lifecycle.market.factory
    base = ContractOffer.from_snapshot(factory.build(candidates[0], 1, "base"))
    offers = tuple(
        RepairableMarketOffer(
            "test-owner",
            f"contract-{index}",
            f"template-{index}",
            replace(base, id=f"contract-{index}"),
            True,
        )
        for index in range(10)
    )
    alternatives = tuple(
        PreparedTemplate(
            f"alternative-{index}",
            snapshot.demands[0].vehicle.model_id,
            snapshot.demands[0].vehicle.city_uid,
            replace(
                ContractOffer.from_snapshot(
                    factory.build(candidate, 1, f"alternative:{index}")
                ),
                id=f"alternative-offer-{index}",
            ),
        )
        for index, candidate in enumerate(candidates[1:], 1)
    )
    return MarketStockRepairContext(
        "test-owner",
        snapshot.demands[0].vehicle.city_uid,
        snapshot.demands[0].vehicle.model_id,
        band,
        offers,
        alternatives,
    )


def _repair_service(contexts):
    """Compose maintenance with the production diversity selector."""
    policy = StockPolicy()
    return MarketStockRepairService(
        MemoryMarketStockRepairStore(contexts),
        MarketStockRepairPlanner(
            policy,
            MarketSelectionService(policy),
        ),
    )


def _persist_context(context, preparation, database):
    """Store one synthetic historical context for repository tests."""
    with database.transaction():
        for item in context.offers:
            preparation.stock.templates.add(
                PreparedTemplate(
                    item.template_id,
                    context.model_id,
                    context.city_uid,
                    item.offer,
                )
            )
            preparation.stock.stock.issue(item.template_id, item.offer)
        for template in context.alternatives:
            preparation.stock.templates.add(template)


def test_market_stock_repair_plans_only_prepared_improvements(
    diverse_stock_game,
):
    """Plan minimal aggregate cleanup and preserve valid repetition."""
    context = _repair_context(diverse_stock_game)

    report = _repair_service((context,)).inspect()

    assert asdict(report) == {
        "checked_contexts": 1,
        "affected_contexts": 1,
        "offers_to_remove": 2,
        "players_to_requeue": 1,
    }
    assert (
        _repair_service((replace(context, alternatives=()),))
        .inspect()
        .offers_to_remove
        == 0
    )
    protected = replace(
        context,
        offers=tuple(
            replace(item, removable=False) for item in context.offers
        ),
    )
    assert _repair_service((protected,)).inspect().offers_to_remove == 0


def test_market_stock_repair_store_reads_source_without_mutation(
    diverse_stock_game,
    database,
):
    """Decode persisted contexts through a query-only source connection."""
    _, preparation, _ = diverse_stock_game
    context = _repair_context(diverse_stock_game)
    _persist_context(context, preparation, database)
    before = sha256(database.path.read_bytes()).hexdigest()

    stored = SqliteMarketStockRepairStore(database.path).contexts()

    assert sha256(database.path.read_bytes()).hexdigest() == before
    selected = next(
        item for item in stored if item.distance_band == context.distance_band
    )
    assert len(selected.offers) == 10
    assert len(selected.alternatives) == 2
    assert all(item.removable for item in selected.offers)


def test_market_stock_repair_creates_reconciled_idempotent_copy(
    diverse_stock_game,
    database,
    tmp_path,
):
    """Preserve gameplay and routing state outside approved stock rows."""
    _, preparation, _ = diverse_stock_game
    context = _repair_context(diverse_stock_game)
    _persist_context(context, preparation, database)
    source_hash = sha256(database.path.read_bytes()).hexdigest()
    target = tmp_path / "repaired.db"
    archive = tmp_path / "removed-stock.jsonl"

    report = build_market_stock_repair(database.path).repair_to(
        target,
        archive,
        1234,
    )

    assert report.offers_to_remove == 2
    assert sha256(database.path.read_bytes()).hexdigest() == source_hash
    assert archive.read_text(encoding="utf-8").count("\n") == 3
    assert build_market_stock_repair(target).inspect().offers_to_remove == 0
    with closing(sqlite3.connect(target)) as output:
        assert output.execute(
            "SELECT count(*) FROM contract_offers"
        ).fetchone() == (8,)
        assert output.execute(
            "SELECT count(*) FROM market_templates"
        ).fetchone() == (12,)
        assert output.execute(
            "SELECT status,next_retry_at FROM market_preparations "
            "WHERE user_id='test-owner'"
        ).fetchone() == ("partial", None)
        assert output.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert output.execute("PRAGMA foreign_key_check").fetchall() == []


def test_market_stock_repair_rolls_back_failed_artifacts(
    diverse_stock_game,
    database,
    tmp_path,
):
    """Remove incomplete output and archive while retaining the source."""
    _, preparation, _ = diverse_stock_game
    _persist_context(
        _repair_context(diverse_stock_game),
        preparation,
        database,
    )
    source_hash = sha256(database.path.read_bytes()).hexdigest()
    service = build_market_stock_repair(database.path)
    target = tmp_path / "failed.db"
    archive = tmp_path / "failed.jsonl"

    with patch.object(
        type(service.store),
        "_compare",
        side_effect=PersistenceError("simulated mismatch"),
    ):
        with pytest.raises(PersistenceError, match="simulated mismatch"):
            service.repair_to(target, archive, 1234)

    assert sha256(database.path.read_bytes()).hexdigest() == source_hash
    assert not target.exists()
    assert not archive.exists()


def test_market_stock_repair_rejects_invalid_source_paths_and_archive(
    diverse_stock_game,
    database,
    tmp_path,
):
    """Reject unsafe paths, corrupt stock context and archive checksum."""
    _, preparation, _ = diverse_stock_game
    _persist_context(
        _repair_context(diverse_stock_game),
        preparation,
        database,
    )
    service = build_market_stock_repair(database.path)
    assert isinstance(service.store, SqliteMarketStockRepairStore)
    plan = service.planner.plan(service.store.contexts())
    with pytest.raises(ValueError, match="must differ"):
        service.store.repair_to(
            plan,
            database.path,
            tmp_path / "archive.jsonl",
            1234,
        )

    inconsistent = tmp_path / "inconsistent.db"
    backup_database(database.path, inconsistent)
    with closing(sqlite3.connect(inconsistent)) as damaged:
        damaged.execute(
            "UPDATE contract_offers SET offer_snapshot=json_set("
            "offer_snapshot,'$.data.origin.city.city_uid',"
            "'00000000-0000-0000-0000-000000000099') "
            "WHERE contract_id='contract-0'"
        )
        damaged.commit()
    with pytest.raises(PersistenceError, match="Marktbestand"):
        SqliteMarketStockRepairStore(inconsistent).contexts()

    wrong_version = tmp_path / "wrong-version.db"
    backup_database(database.path, wrong_version)
    with closing(sqlite3.connect(wrong_version)) as damaged:
        damaged.execute("UPDATE game_schema SET version='unknown'")
        damaged.commit()
    with pytest.raises(PersistenceError, match="Spielstandintegrität"):
        SqliteMarketStockRepairStore(wrong_version).contexts()

    target = tmp_path / "bad-archive.db"
    archive = tmp_path / "bad-archive.jsonl"
    with patch.object(
        type(service.store),
        "_checked_record",
        side_effect=lambda payload: {**payload, "sha256": "invalid"},
    ):
        with pytest.raises(PersistenceError, match="archiv"):
            service.repair_to(target, archive, 1234)
    assert not target.exists() and not archive.exists()


def test_market_stock_repair_reconciliation_rejects_unapproved_changes(
    diverse_stock_game,
    database,
    tmp_path,
):
    """Reject any copied gameplay change outside the approved repair."""
    _, preparation, _ = diverse_stock_game
    _persist_context(
        _repair_context(diverse_stock_game),
        preparation,
        database,
    )
    service = build_market_stock_repair(database.path)
    assert isinstance(service.store, SqliteMarketStockRepairStore)
    plan = service.planner.plan(service.store.contexts())
    target = tmp_path / "reconciled.db"
    archive = tmp_path / "reconciled.jsonl"
    service.repair_to(target, archive, 1234)
    with (
        closing(
            sqlite3.connect(
                database.path.resolve().as_uri() + "?mode=ro",
                uri=True,
            )
        ) as source,
        closing(sqlite3.connect(target)) as output,
    ):
        source.row_factory = output.row_factory = sqlite3.Row
        output.execute("UPDATE player_states SET cash=cash+1")
        output.commit()
        with pytest.raises(PersistenceError, match="Unzulässige"):
            service.store._compare(source, output, plan, 1234)


@pytest.mark.parametrize(
    ("damage", "message"),
    (
        ("schema", "schema"),
        ("offer", "Angebotsbereinigung"),
        ("progress", "Marktfortschritt"),
        ("other-job", "Unbeteiligte"),
        ("affected-job", "neu eingereiht"),
        ("integrity", "inkonsistent"),
    ),
)
def test_market_stock_repair_reconciliation_fences_each_mutable_boundary(
    diverse_stock_game,
    database,
    tmp_path,
    damage,
    message,
):
    """Reject schema, stock, scheduler and integrity deviations separately."""
    _, preparation, _ = diverse_stock_game
    _persist_context(
        _repair_context(diverse_stock_game),
        preparation,
        database,
    )
    with database.transaction(), database.connect() as connection:
        connection.execute("INSERT INTO users VALUES ('other','Other','x',0)")
        connection.execute("INSERT INTO player_states VALUES ('other',1,0,0)")
        connection.execute(
            "INSERT INTO market_preparations VALUES "
            "('other','prep','generation','ready',NULL,1)"
        )
    service = build_market_stock_repair(database.path)
    assert isinstance(service.store, SqliteMarketStockRepairStore)
    plan = service.planner.plan(service.store.contexts())
    target = tmp_path / f"{damage}.db"
    service.repair_to(target, tmp_path / f"{damage}.jsonl", 1234)

    class UnhealthyConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql == "PRAGMA integrity_check":
                return super().execute("SELECT 'simulated corruption'")
            return super().execute(sql, parameters)

    with closing(
        sqlite3.connect(
            database.path.resolve().as_uri() + "?mode=ro",
            uri=True,
        )
    ) as source:
        source.row_factory = sqlite3.Row
        if damage == "integrity":
            with (
                closing(sqlite3.connect(target)) as saved,
                closing(
                    sqlite3.connect(":memory:", factory=UnhealthyConnection)
                ) as output,
            ):
                output.row_factory = sqlite3.Row
                saved.backup(output)
                with pytest.raises(PersistenceError, match=message):
                    service.store._compare(source, output, plan, 1234)
            return
        with closing(sqlite3.connect(target)) as output:
            output.row_factory = sqlite3.Row
            if damage == "schema":
                output.execute("CREATE TABLE unexpected (value TEXT)")
            elif damage == "offer":
                output.execute(
                    "DELETE FROM contract_offers WHERE rowid=("
                    "SELECT rowid FROM contract_offers LIMIT 1)"
                )
            elif damage == "progress":
                output.execute(
                    "INSERT INTO market_stock_cursors VALUES "
                    "('test-owner','unexpected')"
                )
            elif damage == "other-job":
                output.execute(
                    "UPDATE market_preparations SET status='partial' "
                    "WHERE user_id='other'"
                )
            else:
                output.execute(
                    "UPDATE market_preparations SET status='ready' "
                    "WHERE user_id='test-owner'"
                )
            output.commit()
            with pytest.raises(PersistenceError, match=message):
                service.store._compare(source, output, plan, 1234)


def test_market_stock_repair_cli_requires_independent_artifacts(
    diverse_stock_game,
    database,
    tmp_path,
    capsys,
):
    """Keep check read-only and require backup before copy repair."""
    from scripts.repair_market_diversity import main

    _, preparation, _ = diverse_stock_game
    _persist_context(
        _repair_context(diverse_stock_game),
        preparation,
        database,
    )
    source_hash = sha256(database.path.read_bytes()).hexdigest()
    base = [
        "repair_market_diversity.py",
        "--source",
        str(database.path),
    ]
    with patch("sys.argv", [*base, "--check"]):
        main()
    assert json.loads(capsys.readouterr().out)["offers_to_remove"] == 2
    for arguments in (
        [],
        ["--check", "--backup", str(tmp_path / "bad.db")],
        [
            "--backup",
            str(database.path),
            "--output",
            str(tmp_path / "output.db"),
            "--archive",
            str(tmp_path / "archive.jsonl"),
        ],
    ):
        with patch("sys.argv", [*base, *arguments]), pytest.raises(SystemExit):
            main()
    backup = tmp_path / "backup.db"
    output = tmp_path / "output.db"
    archive = tmp_path / "archive.jsonl"
    arguments = [
        *base,
        "--backup",
        str(backup),
        "--output",
        str(output),
        "--archive",
        str(archive),
    ]
    with patch("sys.argv", arguments), patch("time.time", return_value=1234):
        main()
    assert backup.exists() and output.exists() and archive.exists()
    assert sha256(database.path.read_bytes()).hexdigest() == source_hash
