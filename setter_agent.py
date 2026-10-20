import json
import os
import anthropic
from dotenv import load_dotenv
from board_builder import (
    create_random_board,
    validate_chain,
    NUMBER_OF_LINKS_IN_CHAIN,
)
from word_pool import word_pool

load_dotenv()

client = anthropic.Anthropic(api_key = os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-5-5"

def create_hidden_chain_with_llm(board_words, strategy_notes = ""):
    board_words = [
        word.strip().upper() for word in board_words
    ]

    system_prompt = f"""
    You are the setter in a word-association game called CONNECTION.

    Your teammate sees the board words and your starting clue.
    They must guess the intended next word at every step to
    complete your hidden chain.

    Create a chain with:
    - One starting clue that is NOT on the board.
    - Exactly {NUMBER_OF_LINKS_IN_CHAIN} chain words, each selected
    from the board.
    - Each word must connect clearly to the word immediately before it.
    - Prefer common, direct associations that most people would recognize.
    - Avoid links that require unusual explanations or obscure facts.
    - Avoid links where another word on the board could fit just as well.
    - Do not repeat words.

    Return only valid JSON with exactly these fields:
    {{
        "starting_clue": "WORD",
        "chain_words": ["WORD1", "WORD2", "WORD3", "WORD4"],
        "reason_for_each_link": [
            "Reason for link 1",
            "Reason for link 2",
            "Reason for link 3",
            "Reason for link 4"
        ]
    }}
    """

    user_prompt = f"""
    Board words: {board_words}

    Strategy notes from past games:
    {strategy_notes}

    Choose a chain that another person could reasonably guess.
    """

    last_failure_reason = "No valid chain was generated."
    retry_feedback = ""

    for attempt in range(3):
        current_prompt = user_prompt + retry_feedback

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1600,
                thinking={"type": "disabled"},
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": current_prompt
                    }
                ]
            )

            text_blocks = [
                block for block in response.content
                if block.type == "text"
            ]

            response_text = (
                text_blocks[0].text.strip()
                if text_blocks
                else ""
            )

            if not response_text:
                last_failure_reason = (
                    "The setter returned no text response."
                )
                raise ValueError(last_failure_reason)

            # remove Markdown code fences
            if response_text.startswith("```"):
                lines = response_text.splitlines()

                if lines and lines[0].startswith("```"):
                    lines = lines[1:]

                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]

                response_text = "\n".join(lines).strip()

            # parse the first JSON object in the response
            decoder = json.JSONDecoder()
            data, end_position = decoder.raw_decode(response_text)

            if not isinstance(data, dict):
                last_failure_reason = (
                    "The setter response must be a JSON object."
                )
                raise ValueError(last_failure_reason)

            required_fields = [
                "starting_clue",
                "chain_words",
                "reason_for_each_link"
            ]

            if not all(field in data for field in required_fields):
                last_failure_reason = (
                    "The setter response is missing required fields."
                )
                raise ValueError(last_failure_reason)

            starting_clue = data["starting_clue"]
            chain_words = data["chain_words"]
            reasons = data["reason_for_each_link"]

            if not isinstance(starting_clue, str):
                last_failure_reason = (
                    "The starting clue must be a string."
                )
                raise ValueError(last_failure_reason)

            starting_clue = starting_clue.strip().upper()

            if not starting_clue:
                last_failure_reason = (
                    "The starting clue was empty."
                )
                raise ValueError(last_failure_reason)

            if not isinstance(chain_words, list):
                last_failure_reason = (
                    "Chain words must be a list."
                )
                raise ValueError(last_failure_reason)

            if not all(
                isinstance(word, str) for word in chain_words
            ):
                last_failure_reason = (
                    "Every chain word must be a string."
                )
                raise ValueError(last_failure_reason)

            chain_words = [
                word.strip().upper() for word in chain_words
            ]

            if len(chain_words) != NUMBER_OF_LINKS_IN_CHAIN:
                last_failure_reason = (
                    f"The chain must contain exactly "
                    f"{NUMBER_OF_LINKS_IN_CHAIN} words."
                )
                raise ValueError(last_failure_reason)

            if not isinstance(reasons, list):
                last_failure_reason = (
                    "Link reasons must be a list."
                )
                raise ValueError(last_failure_reason)

            if len(reasons) != NUMBER_OF_LINKS_IN_CHAIN:
                last_failure_reason = (
                    "The setter must provide one reason per link."
                )
                raise ValueError(last_failure_reason)

            if not all(
                isinstance(reason, str) and reason.strip()
                for reason in reasons
            ):
                last_failure_reason = (
                    "Every link reason must be a non-empty string."
                )
                raise ValueError(last_failure_reason)

            hidden_chain = [starting_clue] + chain_words

            is_valid, validation_message = validate_chain(
                board_words,
                hidden_chain
            )

            if is_valid:
                return hidden_chain, reasons

            last_failure_reason = validation_message
            raise ValueError(last_failure_reason)

        except json.JSONDecodeError as error:
            last_failure_reason = (
                f"Could not parse setter JSON: {error}"
            )

        except (KeyError, TypeError, ValueError) as error:
            if str(error):
                last_failure_reason = str(error)
            else:
                last_failure_reason = (
                    f"Invalid setter response: {error}"
                )

        except Exception as error:
            last_failure_reason = (
                f"Setter API error: {error}"
            )

        print(
            f"Setter attempt {attempt + 1} failed: "
            f"{last_failure_reason}"
        )

        retry_feedback = (
            f"\nYour previous attempt was rejected because: "
            f"{last_failure_reason}\n"
            "Generate a new chain that fixes this specific problem. "
            "Return only the required JSON object."
        )

    return None, last_failure_reason


if __name__ == "__main__":
    for batch_id in range(1, 6):
        board = create_random_board(word_pool)

        hidden_chain, reasons = create_hidden_chain_with_llm(
            board,
            strategy_notes=""
        )

        print(f"\n--- Trial {batch_id} ---")
        print("Board:", board)

        if hidden_chain is None:
            print("Failed to create a valid chain:", reasons)
            continue

        print("Hidden chain:", " -> ".join(hidden_chain))
        print("Reasons for each link:")

        for index, reason in enumerate(reasons, start=1):
            print(f"{index}. {reason}")