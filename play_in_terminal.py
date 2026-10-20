from connection_rules import create_new_game_state, get_current_clue, submit_guess

board = [
    "OCEAN", "PILOT", "SAND", "AIRPLANE",
    "BEACH", "ENGINE", "WATER", "RUNWAY",
    "DESERT", "CLOUD", "WAVE", "HELICOPTER",
    "FISH", "WIND", "SHIP", "AIRPORT"
]

hidden_chain = [
    "TRAVEL",
    "AIRPLANE",
    "PILOT",
    "AIRPORT",
    "RUNWAY"
]

game_state = create_new_game_state(board, hidden_chain)

print("Welcome to CONNECTION!")
print()
print("Your board:")
for word in board:
    print(word)
print("Starting clue:", get_current_clue(game_state))
print("Lives:", game_state["lives_remaining"])

while not game_state["is_game_over"]:
    guess = input("Choose a word: ").upper()
    outcome = submit_guess(game_state, guess)
    print("You chose:", guess)
    if outcome == "correct":
        print("Yes!")
        print(f"Next clue: {get_current_clue(game_state)}")
    elif outcome == "wrong":
        print("Wrong. Try again.")
        print(f"You have {game_state['lives_remaining']} lives remaining.")
    elif outcome == "not_on_board":
        print("Word is not on board. No life lost.")
    elif outcome == "already_used":
        print("You have already used this word. No life lost.")
    elif outcome == "chain_complete":
        print("You got it! Game over.")
    elif outcome == "out_of_lives":
        print("Better luck next time.")
