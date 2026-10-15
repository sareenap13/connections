from connection_rules import create_new_game_state, get_current_clue, submit_guess
 
# Starting clue is deliberately not on the board
example_board_words = [
    "APPLE", "MOON", "COURT", "TURKEY", "PIZZA", "BAT", "RAIN", "PARIS",
    "GLASS", "BASKETBALL", "ROSE", "SHARK", "DESERT", "PIANO", "TIGER", "DRAGON",
]
example_hidden_chain = ["SPORTS", "BASKETBALL", "COURT", "PARIS", "DRAGON"]
 
 
def check_outcome(description_of_step, actual_outcome_label, expected_outcome_label):
    passed_or_failed = "PASS" if actual_outcome_label == expected_outcome_label else "FAIL"
    print(f"{passed_or_failed}  {description_of_step}: expected {expected_outcome_label}, got {actual_outcome_label}")
 
 
# ---------- Game 1: play the full chain with every kind of guess along the way ----------
print("Game 1: full chain")
winning_game_state = create_new_game_state(example_board_words, example_hidden_chain)
 
check_outcome("starting clue", get_current_clue(winning_game_state), "SPORTS")
check_outcome("first correct link", submit_guess(winning_game_state, "BASKETBALL"), "correct")
check_outcome("clue moves forward", get_current_clue(winning_game_state), "BASKETBALL")
check_outcome("word not on board", submit_guess(winning_game_state, "ELEPHANT"), "not_on_board")
check_outcome("repeat a used word", submit_guess(winning_game_state, "BASKETBALL"), "already_used")
check_outcome("lives unchanged by invalid guesses", winning_game_state["lives_remaining"], 3)
check_outcome("lowercase correct guess", submit_guess(winning_game_state, "court"), "correct")
check_outcome("wrong guess", submit_guess(winning_game_state, "PIANO"), "wrong")
check_outcome("wrong guess costs a life", winning_game_state["lives_remaining"], 2)
check_outcome("third correct link", submit_guess(winning_game_state, "PARIS"), "correct")
check_outcome("last link finishes chain", submit_guess(winning_game_state, "DRAGON"), "chain_complete")
check_outcome("guess after game ends", submit_guess(winning_game_state, "APPLE"), "game_over")
check_outcome("used words in order", winning_game_state["used_words"], ["BASKETBALL", "COURT", "PARIS", "DRAGON"])
 
# ---------- Game 2: lose all three lives ----------
print("\nGame 2: run out of lives")
losing_game_state = create_new_game_state(example_board_words, example_hidden_chain)
 
check_outcome("first wrong guess", submit_guess(losing_game_state, "APPLE"), "wrong")
check_outcome("second wrong guess", submit_guess(losing_game_state, "MOON"), "wrong")
check_outcome("third wrong guess ends game", submit_guess(losing_game_state, "RAIN"), "out_of_lives")
check_outcome("correct word after losing", submit_guess(losing_game_state, "BASKETBALL"), "game_over")
 
# ---------- Game 3: creating a game must not change the original lists ----------
print("\nGame 3: original lists stay untouched")
board_length_before_play = len(example_board_words)
copy_check_game_state = create_new_game_state(example_board_words, example_hidden_chain)
submit_guess(copy_check_game_state, "BASKETBALL")
check_outcome("original board length unchanged", len(example_board_words), board_length_before_play)
check_outcome("original chain unchanged", example_hidden_chain, ["SPORTS", "BASKETBALL", "COURT", "PARIS", "DRAGON"])
