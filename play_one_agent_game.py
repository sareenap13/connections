from connection_rules import create_new_game_state, get_current_clue, submit_guess
from guesser_agent import choose_next_word_with_llm, MODEL
from datetime import datetime
from word_pool import word_pool
from board_builder import create_board_around_fixed_chain

def play_one_agent_game(board_words, hidden_chain, guesser_model):
    game_state = create_new_game_state(board_words, hidden_chain)
    max_turns = 20
    turn_count = 0
    moves = []
    wrong_guesses = []
    while game_state["is_game_over"] is False and turn_count < max_turns:
        turn_count += 1
        current_clue = get_current_clue(game_state)
        agent_response = choose_next_word_with_llm(board_words, current_clue,
                    game_state["used_words"], wrong_guesses,
                    game_state["lives_remaining"], guesser_model = guesser_model)

        chosen_word = agent_response["chosen_word"]
        reason_for_connection = agent_response["reason_for_connection"]
        if chosen_word is None:
            print("Clue: ", current_clue)
            print("Agent response failed: ", reason_for_connection)
            moves.append({
                "clue": current_clue,
                "chosen_word": None,
                "reason": reason_for_connection,
                "outcome": "agent_response_failed"
            })
            continue
        
        outcome = submit_guess(game_state, chosen_word)
        if outcome in ["wrong", "out_of_lives"]:
            wrong_guesses.append(chosen_word)
        moves.append({
                        "clue": current_clue,
                        "chosen_word": chosen_word,
                        "reason": reason_for_connection,
                        "outcome": outcome
                    })
        print("Clue: ", current_clue)
        print("Chosen word: ", chosen_word)
        print("Reason: ", reason_for_connection)
        print("Outcome: ", outcome)

    
    if game_state["is_game_over"] is True:
        if game_state["lives_remaining"] == 0:
            final_result = "out_of_lives"
        else:
            final_result = "chain_complete"
    elif turn_count >= max_turns:
        final_result = "turn_limit_reached"
    else:
        final_result = "agent_response_failed"
    
    print("Final result: ", final_result)
    print("Hidden chain: ", hidden_chain)
    print("Lives remaining: ", game_state["lives_remaining"])

    
    correct_count = sum(
        1 for move in moves
        if move["outcome"] in ["correct", "chain_complete"]
    )

    wrong_count = sum(
        1 for move in moves
        if move["outcome"] in ["wrong", "out_of_lives"]
    )

    total_guesses = correct_count + wrong_count

    game_result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "starting_clue": hidden_chain[0],
        "hidden_chain": hidden_chain,
        "final_result": final_result,
        "lives_remaining": game_state["lives_remaining"],
        "total_guesses": total_guesses,
        "correct_guesses": correct_count,
        "wrong_guesses": wrong_count,
        "moves": moves
    }

    return game_result

if __name__ == "__main__":
    hidden_chain = [
        "TRAVEL",
        "AIRPLANE",
        "PILOT",
        "AIRPORT",
        "RUNWAY"
    ]

    board = create_board_around_fixed_chain(hidden_chain, word_pool)

    print("Generated board:", board)
    print("Number of board words:", len(board))

    play_one_agent_game(board, hidden_chain, MODEL)