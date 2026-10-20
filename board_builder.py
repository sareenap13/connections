import random
NUMBER_OF_LINKS_IN_CHAIN = 4

def create_board_around_fixed_chain(hidden_chain, word_pool, board_size = 16):
    # the starting clue is not on the board
    answer_words = hidden_chain[1:]

    if len(answer_words) > board_size:
        raise ValueError("The hidden chain is too long for this board.")

    # remove duplicates and exclude all hidden-chain words
    # from the distractor pool
    available_words = list(dict.fromkeys(
        word for word in word_pool
        if word not in hidden_chain
    ))

    distractor_count = board_size - len(answer_words)

    if len(available_words) < distractor_count:
        raise ValueError("Not enough words to fill the board.")

    # select distractors and combine them with the answers
    distractors = random.sample(
        available_words,
        distractor_count
    )

    board = answer_words + distractors

    # shuffle so the intended answers are not grouped together
    random.shuffle(board)

    return board

def create_random_board(word_pool, board_size=16):
    unique_words = list(dict.fromkeys(word_pool))

    if len(unique_words) < board_size:
        raise ValueError("Not enough unique words in the word pool.")

    return random.sample(unique_words, board_size)


def validate_chain(board, hidden_chain):
    if len(hidden_chain) != NUMBER_OF_LINKS_IN_CHAIN + 1:
        return False, (
            "The chain must contain a starting clue and "
            f"{NUMBER_OF_LINKS_IN_CHAIN} links."
        )

    if len(set(board)) != len(board):
        return False, "The board cannot contain duplicate words."

    if hidden_chain[0] in board:
        return False, "The starting clue must not be on the board."

    if len(set(hidden_chain)) != len(hidden_chain):
        return False, "The chain cannot repeat words."

    for word in hidden_chain[1:]:
        if word not in board:
            return False, f"{word} is not on the board."

    return True, "Chain is valid."
