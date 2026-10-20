import json
from collections import defaultdict

with open("game_results.json", "r") as file:
    results = json.load(file)

total_games = len(results)

completed_games = sum(
    1 for game in results
    if game["final_result"] == "chain_complete"
)

total_wrong_guesses = 0
total_invalid_moves = 0

link_stats = defaultdict(
    lambda: {"mistakes": 0, "attempts": 0}
)

for game in results:
    hidden_chain = game["hidden_chain"]

    for move in game["moves"]:
        outcome = move["outcome"]
        clue = move["clue"]
        guessed_word = move["chosen_word"]

        if outcome in ["wrong", "out_of_lives"]:
            total_wrong_guesses += 1
        elif outcome in ["not_on_board", "already_used"]:
            total_invalid_moves += 1

        if outcome not in ["correct", "chain_complete",
                           "wrong", "out_of_lives"]:
            continue

        if guessed_word is None:
            continue

        if clue not in hidden_chain:
            continue

        position = hidden_chain.index(clue)

        if position + 1 >= len(hidden_chain):
            continue

        intended_word = hidden_chain[position + 1]
        link = (clue, intended_word)

        link_stats[link]["attempts"] += 1

        if outcome in ["wrong", "out_of_lives"]:
            link_stats[link]["mistakes"] += 1

print("Total games:", total_games)
print("Completed games:", completed_games)
print("Total wrong guesses:", total_wrong_guesses)
print("Total invalid moves:", total_invalid_moves)

if total_games > 0:
    completion_rate = completed_games / total_games * 100
    average_wrong_guesses = total_wrong_guesses / total_games

    print("Chain completion rate:", round(completion_rate, 1), "%")
    print("Average wrong guesses per game:",
          round(average_wrong_guesses, 2))

print("\nLink difficulty:")

for (clue, intended_word), stats in link_stats.items():
    print(
        f"{clue} -> {intended_word}: "
        f"{stats['mistakes']} association mistakes out of "
        f"{stats['attempts']} valid guesses"
    )