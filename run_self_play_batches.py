import json
from datetime import datetime, timezone
from board_builder import create_random_board
from setter_agent import create_hidden_chain_with_llm
from play_one_agent_game import play_one_agent_game
from guesser_agent import MODEL as GUESSER_MODEL
from word_pool import word_pool
from setter_agent import update_setter_strategy_notes

PAIRED_GUESSER_MODEL = GUESSER_MODEL
HELD_OUT_GUESSER_MODEL = "gpt-5-mini"

# experiment settings
NUMBER_OF_BATCHES = 10
GAMES_PER_BATCH = 10
LOG_FILE = "game_logs.jsonl"

def append_record(record):
    """Append one game record to the JSONL log immedimately."""
    with open(LOG_FILE, "a", encoding = "utf-8") as file:
        file.write(json.dumps(record) + "\n")

def summarize_paired_games(paired_games):
    summaries = []

    for game in paired_games:
        if game.get("status") != "played":
            continue

        if game.get("guesser_role") != "paired":
            continue

        # Do not learn from games that ended because of
        # a technical response failure.
        if game.get("final_result") in [
            "agent_response_failed",
            "turn_limit_reached",
        ] and any(
            move.get("outcome") == "agent_response_failed"
            for move in (game.get("moves") or [])
        ):
            continue

        chain = game.get("hidden_chain") or []
        reasons = game.get("setter_reasons") or []
        moves = game.get("moves") or []

        link_summaries = []

        for index in range(len(chain) - 1):
            source_word = chain[index]
            intended_word = chain[index + 1]

            relevant_moves = [
                {
                    "chosen_word": move.get("chosen_word"),
                    "reason": move.get("reason"),
                    "outcome": move.get("outcome"),
                }
                for move in moves
                 if (move.get("clue") or "").upper() == source_word
            ]

            if not relevant_moves:
                continue

            found = any(
                (move.get("chosen_word") or "").upper() == intended_word
                and move.get("outcome") in [
                    "correct",
                    "chain_complete"
                ]
                for move in relevant_moves
            )

            link_reached = len(relevant_moves) > 0
            link_summaries.append({
                "link": f"{source_word} -> {intended_word}",
                "setter_reason": (
                    reasons[index]
                    if index < len(reasons)
                    else None
                ),
                "link_reached": link_reached,
                "guesser_reached_this_link": len(relevant_moves) > 0,
                "intended_word_found": found,
                "guesser_attempts": relevant_moves
            })

        summaries.append({
            "batch_number": game.get("batch_number"),
            "game_number": game.get("game_number"),
            "starting_clue": chain[0] if chain else None,
            "final_result": game.get("final_result"),
            "links": link_summaries,
        })
    return summaries


def append_strategy_history(batch_number, version, strategy_notes):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "batch_number": batch_number,
        "strategy_notes_version": version,
        "strategy_notes": strategy_notes,
    }

    with open(
        "strategy_notes_history.jsonl",
        "a",
        encoding="utf-8",
    ) as file:
        file.write(json.dumps(record) + "\n")

def create_base_record(run_id, batch_number, game_number, board, strategy_notes,
                       strategy_notes_version, guesser_model = None, guesser_role = None):
    """Create metadata shared by every game record."""
    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "batch_number": batch_number,
        "game_number": game_number,
        "guesser_model": guesser_model,
        "guesser_role": guesser_role,
        "board_words": board,
        "setter_reasons": None,
        "strategy_notes": strategy_notes,
        "strategy_notes_version": strategy_notes_version,
    }

def run_self_play_batches():
    strategy_notes = ""
    strategy_notes_version = 0
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    print(f"Experiment run ID: {run_id}")
    
    for batch_number in range(1, NUMBER_OF_BATCHES + 1):
        completed_games = {"paired": 0, "held_out": 0}
        skipped_games = {"paired": 0, "held_out": 0}
        paired_feedback_games = []

        print(f"\n========== Batch {batch_number} ==========")

        for game_number in range(1, GAMES_PER_BATCH + 1):
            board = create_random_board(word_pool)

            record = create_base_record(
                run_id,
                batch_number,
                game_number,
                board,
                strategy_notes,
                strategy_notes_version
            )

            print(
                f"\nBatch {batch_number}, "
                f"Game {game_number}/{GAMES_PER_BATCH}"
            )

             # ask setter to create a chain for this board
            hidden_chain, reasons = create_hidden_chain_with_llm(
                board,
                strategy_notes = strategy_notes,
            )

            # log failed chain generation and move to the next game
            if hidden_chain is None:
                record.update({
                    "status": "skipped",
                    "final_result": "skipped",
                    "skip_reason": reasons,
                    "hidden_chain": None,
                })

                append_record(record)

                for guesser_role, guesser_model in [
                    ("paired", PAIRED_GUESSER_MODEL),
                    ("held_out", HELD_OUT_GUESSER_MODEL),
                ]:
                    skipped_games[guesser_role] += 1

                print(f"Skipped game: {reasons}")
                continue

            record["hidden_chain"] = hidden_chain
            record["setter_reasons"] = reasons

            print("Hidden chain:", " -> ".join(hidden_chain))

            guessers = [
                ("paired", PAIRED_GUESSER_MODEL),
                ("held_out", HELD_OUT_GUESSER_MODEL),
            ]

            for guesser_role, guesser_model in guessers:
                print(
                    f"\nPlaying as {guesser_role} "
                    f"using {guesser_model}"
                )

                record = create_base_record(
                    run_id,
                    batch_number,
                    game_number,
                    board,
                    strategy_notes,
                    strategy_notes_version,
                    guesser_model = guesser_model,
                    guesser_role = guesser_role,
                )

                record["hidden_chain"] = hidden_chain
                record["setter_reasons"] = reasons

                try:
                    game_result = play_one_agent_game(
                        board,
                        hidden_chain,
                        guesser_model,
                    )

                    if not isinstance(game_result, dict):
                        raise TypeError(
                            "play_one_agent_game() did not return "
                            "a game-result dictionary."
                        )

                    record.update(game_result)

                    # Restore experiment metadata.
                    record.update({
                        "batch_number": batch_number,
                        "game_number": game_number,
                        "guesser_model": guesser_model,
                        "guesser_role": guesser_role,
                        "board_words": board,
                        "hidden_chain": hidden_chain,
                        "setter_reasons": reasons,
                        "strategy_notes": strategy_notes,
                        "strategy_notes_version": strategy_notes_version,
                        "status": "played",
                    })

                    append_record(record)

                    if guesser_role == "paired":
                        paired_feedback_games.append(record)

                    if record["final_result"] == "chain_complete":
                        completed_games[guesser_role] += 1

                    print(
                        f"{guesser_role} result: "
                        f"{record['final_result']}"
                    )

                except Exception as error:
                    record.update({
                        "status": "error",
                        "final_result": "error",
                        "error": str(error),
                    })

                    append_record(record)
                    skipped_games[guesser_role] += 1

                    print(
                        f"{guesser_role} game error: {error}"
                    )
                # Reflect using paired games only.
        paired_summaries = summarize_paired_games(
            paired_feedback_games
        )

        if paired_summaries:
            print("\nUpdating setter strategy notes...")

            updated_notes = update_setter_strategy_notes(
                strategy_notes,
                paired_summaries,
            )

            if updated_notes != strategy_notes:
                strategy_notes = updated_notes
                strategy_notes_version += 1

                append_strategy_history(
                    batch_number,
                    strategy_notes_version,
                    strategy_notes,
                )

                print(
                    "Strategy notes updated to version "
                    f"{strategy_notes_version}."
                )
                print("Updated notes:", strategy_notes)

            else:
                print(
                    "Strategy notes unchanged. "
                    "Keeping the current version."
                )

        else:
            print(
                "No successful paired games to learn from. "
                "Strategy notes unchanged."
            )
        
        for guesser_role in ["paired", "held_out"]:
            print(
                f"\nBatch {batch_number}, {guesser_role}: "
                f"{completed_games[guesser_role]}/{GAMES_PER_BATCH} "
                f"chains completed, "
                f"{skipped_games[guesser_role]} skipped or errored."
            )


if __name__ == "__main__":
    run_self_play_batches()
