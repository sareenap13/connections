import json
from collections import defaultdict
import matplotlib.pyplot as plt

LOG_FILE = "game_logs.jsonl"

def load_results():
    with open(LOG_FILE, "r", encoding = "utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]

def select_latest_run(results):
    run_ids = sorted({
        game.get("run_id")
        for game in results
        if game.get("run_id")
    })

    print("\n========== EXPERIMENT RUNS ==========")

    for run_id in run_ids:
        print(run_id)

    if not run_ids:
        print("No run IDs found. Analyzing all historical records.")
        return results

    latest_run_id = run_ids[-1]

    print(f"\nAnalyzing run: {latest_run_id}")

    return [
        game for game in results
        if game.get("run_id") == latest_run_id
    ]

def get_moves(game):
    return game.get("moves") or []

def analyze_results(results):
    played_games = [
        game for game in results
        if game.get("status") == "played"
    ]

    skipped_games = [
        game for game in results
        if game.get("status") == "skipped"
    ]

    errored_games = [
        game for game in results
        if game.get("status") == "error"
    ]

    games_with_agent_failures = [
        game for game in played_games
        if any(
            move.get("outcome") == "agent_response_failed"
            for move in get_moves(game)
        )
    ]

    failed_turns = sum(
        1
        for game in played_games
        for move in get_moves(game)
        if move.get("outcome") == "agent_response_failed"
    )

    # Exclude games that hit the turn limit because of response failures.
    performance_games = [
        game for game in played_games
        if not (
            game.get("final_result") in [
                "turn_limit_reached",
                "agent_response_failed",
            ]
            and any(
                move.get("outcome") == "agent_response_failed"
                for move in get_moves(game)
            )
        )
    ]

    completed_performance_games = [
        game for game in performance_games
        if game.get("final_result") == "chain_complete"
    ]

    total_correct = 0
    total_wrong = 0
    total_invalid = 0

    # compare two guesser roles
    role_stats = defaultdict(
        lambda: {
            "played": 0,
            "completed": 0,
            "correct": 0,
            "wrong": 0,
            "invalid": 0,
            "links_found": 0
        }
    )

    # track mistakes for each intended chain link
    link_stats = defaultdict(
        lambda: {"mistakes": 0, "attempts": 0}
    )

    # track performance by link position
    position_stats = defaultdict(
        lambda: {"correct": 0, "wrong": 0}
    )

    for game in performance_games:
        role = game.get("guesser_role", "unknown")
        stats = role_stats[role]

        stats["played"] += 1

        if game.get("final_result") == "chain_complete":
            stats["completed"] += 1

        hidden_chain = game.get("hidden_chain") or []

        links_found = sum(
            1
            for move in get_moves(game)
            if move.get("outcome") in ["correct", "chain_complete"]
        )
        stats["links_found"] += links_found

        for move in get_moves(game):
            outcome = move.get("outcome")
            clue = move.get("clue")
            guessed_word = move.get("chosen_word")

            if outcome in ["correct", "chain_complete"]:
                total_correct += 1
                stats["correct"] += 1
            elif outcome in ["wrong", "out_of_lives"]:
                total_wrong += 1
                stats["wrong"] += 1
            elif outcome in ["not_on_board", "already_used"]:
                total_invalid += 1
                stats["invalid"] += 1

            # analyze only guesses with a known intended link
            if outcome not in [
                "correct",
                "chain_complete",
                "wrong",
                "out_of_lives",
            ]:
                continue

            if guessed_word is None or clue not in hidden_chain:
                continue

            position = hidden_chain.index(clue)

            if position + 1 >= len(hidden_chain):
                continue

            intended_word = hidden_chain[position + 1]
            link = (clue, intended_word)

            link_stats[link]["attempts"] += 1

            if outcome in ["wrong", "out_of_lives"]:
                link_stats[link]["mistakes"] += 1

            # position 1 means the first link after the starting clue
            position_number = position + 1

            if outcome in ["correct", "chain_complete"]:
                position_stats[position_number]["correct"] += 1
            else:
                position_stats[position_number]["wrong"] += 1

    # summary
    
    print("\n========== OVERALL RESULTS ==========")
    print("Total log records:", len(results))
    print("Games played:", len(played_games))
    print("Games with agent response failures:", len(games_with_agent_failures))
    print("Failed response turns:", failed_turns)
    print("Valid performance attempts:", len(performance_games))
    print("Chains completed:", len(completed_performance_games))
    print("Setter skips:", len(skipped_games))
    print("Game errors:", len(errored_games))

    if performance_games:
        completion_rate = (
            len(completed_performance_games)
            / len(performance_games) * 100
        )

        print(f"Completion rate: {completion_rate:.1f}%")
        print("Total correct guesses:", total_correct)
        print("Total wrong guesses:", total_wrong)
        print("Total invalid moves:", total_invalid)
        print(
            "Average correct guesses per game:",
            round(total_correct / len(performance_games), 2)
        )
        print(
            "Average wrong guesses per game:",
            round(total_wrong / len(performance_games), 2)
        )

    # compare paired versus held-out
    print("\n========== RESULTS BY GUESSER ROLE ==========")

    for role in ["paired", "held_out", "unknown"]:
        if role not in role_stats:
            continue

        stats = role_stats[role]
        role_games = [
            game for game in performance_games
            if game.get("guesser_role", "unknown") == role
        ]
        played = len(role_games)
        completed = sum(
            1 for game in role_games
            if game.get("final_result") == "chain_complete"
        )
        rate = completed / played * 100 if played else 0

        print(f"\n{role.upper()}:")
        print(f"  Model: {next((
            game.get('guesser_model', 'unknown')
            for game in played_games
            if game.get('guesser_role', 'unknown') == role
        ), 'unknown')}")
        print(f"  Games played: {played}")
        print(f"  Chains completed: {completed}")
        print(f"  Completion rate: {rate:.1f}%")

        if played:
            print(
                "  Average correct guesses:",
                round(stats["correct"] / played, 2)
            )
            print(
                "  Average wrong guesses:",
                round(stats["wrong"] / played, 2)
            )

    # batch-by-batch comparison, split by role
    print("\n========== RESULTS BY BATCH AND ROLE ==========")

    batch_stats = defaultdict(
        lambda: defaultdict(
            lambda: {
                "played": 0,
                "completed": 0,
                "skipped": 0,
                "errors": 0,
                "agent_failures": 0,
                "correct": 0,
                "wrong": 0,
                "links_found": 0
            }
        )
    )

    for game in results:
        batch = game.get("batch_number", "unknown")
        role = game.get("guesser_role", "unknown")
        stats = batch_stats[batch][role]
        status = game.get("status")

        if status == "played" and game not in performance_games:
            stats["agent_failures"] += 1
            continue
        if status == "skipped":
            stats["skipped"] += 1
        elif status == "error":
            stats["errors"] += 1
        elif status == "played":
            stats["played"] += 1

            stats["links_found"] += sum(
                1
                for move in get_moves(game)
                if move.get("outcome") in ["correct", "chain_complete"]
            )

            if game.get("final_result") == "chain_complete":
                stats["completed"] += 1

            stats["correct"] += game.get("correct_guesses", 0)
            stats["wrong"] += game.get("wrong_guesses", 0)

    for batch in sorted(batch_stats, key=str):
        print(f"\nBatch {batch}:")

        for role, stats in sorted(batch_stats[batch].items(), key=lambda item: str(item[0])):
            played = stats["played"]
            completed = stats["completed"]
            rate = completed / played * 100 if played else 0

            print(
                f"  {role}: {completed}/{played} completed "
                f"({rate:.1f}%), "
                f"skipped={stats['skipped']}, "
                f"errors={stats['errors']}, "
                f"agent_failures={stats['agent_failures']}, "
                f"correct={stats['correct']}, "
                f"wrong={stats['wrong']}"
            )

            average_links = (
                stats["links_found"] / played
                if played else 0
            )

            print(
                f"  Average links found: "
                f"{average_links:.2f}/4"
            )

    # compare paired and held-out guessers on the same chain
    print("\n========== SAME-CHAIN COMPARISON ==========")

    chain_pairs = defaultdict(dict)

    for game in performance_games:
        role = game.get("guesser_role")
        if role not in ["paired", "held_out"]:
            continue

        # use chain and board to identify the shared setter task
        # batch and game numbers distinguish ordinary game slots
        key = (
            game.get("batch_number"),
            game.get("game_number"),
            tuple(game.get("board_words") or []),
            tuple(game.get("hidden_chain") or []),
        )

        chain_pairs[key][role] = game

    comparisons = 0
    paired_wins = 0
    held_out_wins = 0
    ties = 0

    for key, pair in chain_pairs.items():
        if "paired" not in pair or "held_out" not in pair:
            continue

        comparisons += 1
        paired = pair["paired"]
        held_out = pair["held_out"]

        paired_complete = (
            paired.get("final_result") == "chain_complete"
        )
        held_out_complete = (
            held_out.get("final_result") == "chain_complete"
        )

        if paired_complete and not held_out_complete:
            paired_wins += 1
            outcome = "paired completed; held-out did not"
        elif held_out_complete and not paired_complete:
            held_out_wins += 1
            outcome = "held-out completed; paired did not"
        elif paired_complete and held_out_complete:
            ties += 1
            outcome = "both completed"
        else:
            ties += 1
            outcome = "neither completed"

        chain = " -> ".join(paired.get("hidden_chain") or [])
        print(f"  {chain}: {outcome}")

    print(f"\nMatched chains: {comparisons}")
    print(f"Paired-only completions: {paired_wins}")
    print(f"Held-out-only completions: {held_out_wins}")
    print(f"Both completed or neither completed: {ties}")

    # link difficulty
    print("\n========== LINK DIFFICULTY ==========")

    for (clue, intended_word), stats in sorted(link_stats.items()):
        attempts = stats["attempts"]
        mistakes = stats["mistakes"]
        mistake_rate = mistakes / attempts * 100 if attempts else 0

        print(
            f"{clue} -> {intended_word}: "
            f"{mistakes} mistakes out of {attempts} guesses "
            f"({mistake_rate:.1f}% mistake rate)"
        )

    # mistakes by chain position
    print("\n========== RESULTS BY LINK POSITION ==========")

    for position, stats in sorted(position_stats.items()):
        total = stats["correct"] + stats["wrong"]
        mistakes = stats["wrong"]
        mistake_rate = mistakes / total * 100 if total else 0

        print(
            f"Link {position}: "
            f"{stats['correct']} correct, {mistakes} wrong "
            f"({mistake_rate:.1f}% wrong)"
        )

    # individual games
    print("\n========== INDIVIDUAL GAMES ==========")

    for game in results:
        chain = " -> ".join(game.get("hidden_chain") or [])

        print(
            f"Batch {game.get('batch_number', '?')}, "
            f"Game {game.get('game_number', '?')}, "
            f"Role={game.get('guesser_role', 'unknown')}, "
            f"Model={game.get('guesser_model', 'unknown')}, "
            f"Status={game.get('status', 'unknown')}, "
            f"Result={game.get('final_result', 'unknown')}, "
            f"Chain={chain}"
        )

def plot_links_found(results):
    batch_stats = defaultdict(
        lambda: defaultdict(list)
    )

    for game in results:
        if game.get("status") != "played":
            continue

        if (
            game.get("final_result") in [
                "turn_limit_reached",
                "agent_response_failed",
            ]
            and any(
                move.get("outcome") == "agent_response_failed"
                for move in get_moves(game)
            )
        ):
            continue

        if (
            game.get("final_result") == "turn_limit_reached"
            and any(
                move.get("outcome") == "agent_response_failed"
                for move in get_moves(game)
            )
        ):
            continue

        role = game.get("guesser_role")
        if role not in ["paired", "held_out"]:
            continue

        batch = game.get("batch_number", "unknown")

        links_found = sum(
            1
            for move in get_moves(game)
            if move.get("outcome") in ["correct", "chain_complete"]
        )

        batch_stats[batch][role].append(links_found)

    batches = sorted(batch_stats, key=lambda value: int(value))
    roles = ["paired", "held_out"]

    for role in roles:
        x_values = []
        averages = []

        for batch in batches:
            scores = batch_stats[batch].get(role, [])

            if scores:
                x_values.append(batch)
                averages.append(sum(scores) / len(scores))

        if x_values:
            plt.plot(
                x_values,
                averages,
                marker="o",
                label=role,
            )

    plt.xlabel("Batch")
    plt.ylabel("Average links found (out of 4)")
    plt.title("Setter Learning: Links Found per Batch")
    plt.ylim(0, 4)
    plt.xticks(batches)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("links_found_by_batch.png")
    plt.show()

if __name__ == "__main__":
    results = load_results()
    results = select_latest_run(results)
    analyze_results(results)
    plot_links_found(results)