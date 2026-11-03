"""Account isolation, security, persistence and concurrent economy tests."""

from app.bootstrap import (
    build_leaderboard_reader,
    build_player_context,
)
from app.domain.game import PlayerState
from app.repositories.accounts import AccountRepository
from tests.transport_fixtures import add_transport

PASSWORD = "test-only-password-42"


def test_leaderboard_counts_offline_arrivals_without_double_counting(
    database, synthetic_runtime, synthetic_game
):
    accounts = AccountRepository(database)
    alice = accounts.create_user("Alice", "unused")
    accounts.create_user("Bob", "unused")
    context = build_player_context(synthetic_runtime, alice["id"])
    context.state_repository.save_player(
        PlayerState(cash=175000, completed=2, reputation=2)
    )
    service = context.game
    add_transport(service, payout=100, context=context)
    reader = build_leaderboard_reader(synthetic_runtime)
    assert list(reader.list_ranking(synthetic_game.now())) == [
        {"username": "Alice", "completed": 3},
        {"username": "TestOwner", "completed": 0},
        {"username": "Bob", "completed": 0},
    ]
    service.reconcile_arrival()
    assert reader.list_ranking(synthetic_game.now())[0]["completed"] == 3
