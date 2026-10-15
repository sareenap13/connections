def create_new_game_state(board_words, hidden_chain):
    board_words = board_words.copy()
    hidden_chain = hidden_chain.copy()
    current_position = 0
    lives = 3
    used_words = []
    is_game_over = False

    return {
    "board_words": board_words,
    "hidden_chain": hidden_chain,
    "current_chain_position": current_position,
    "lives_remaining": lives,
    "used_words": used_words,
    "is_game_over": is_game_over
    }


def get_current_clue(game_state):
    return game_state["hidden_chain"][game_state["current_chain_position"]]

def submit_guess(game_state, guessed_word):
    guessed_word = guessed_word.upper()
    if game_state["is_game_over"] == True:
        return "game_over"
    elif guessed_word not in game_state["board_words"]:
        return "not_on_board"
    elif guessed_word in game_state["used_words"]:
        return "already_used"

    next_word = game_state["hidden_chain"][game_state["current_chain_position"] + 1]
    if guessed_word == next_word:
        game_state["used_words"].append(guessed_word)
        game_state["current_chain_position"] += 1
        if game_state["current_chain_position"] == len(game_state["hidden_chain"]) - 1:
            game_state["is_game_over"] = True
            return "chain_complete"
        else:
            return "correct"
    else:
        game_state["lives_remaining"] -= 1
        if game_state["lives_remaining"] == 0:
            game_state["is_game_over"] = True
            return "out_of_lives"
        else:
            return "wrong"