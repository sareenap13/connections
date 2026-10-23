import json
import os
import anthropic
from openai import OpenAI
from dotenv import load_dotenv
from board_builder import create_random_board, validate_chain, NUMBER_OF_LINKS_IN_CHAIN
from word_pool import word_pool

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "claude-haiku-5-5"

def get_text_response_from_setter_model(setter_model, system_prompt, user_prompt,
                                        max_output_tokens, use_thinking = False):
    if setter_model.startswith("claude"):
        if use_thinking:
            response = client.messages.create(
                model = setter_model,
                max_tokens = 4000,
                thinking = {"type": "adaptive"},
                extra_body = {"output_config": {"effort": "medium"}},
                system = system_prompt,
                messages = [{"role": "user", "content": user_prompt}],
            )
        else:
            response = client.messages.create(
                model = setter_model,
                max_tokens = max_output_tokens,
                thinking = {"type": "disabled"},
                system = system_prompt,
                messages = [{"role": "user", "content": user_prompt}],
            )

        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

    if setter_model.startswith("gpt"):
        response = openai_client.responses.create(
            model=setter_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.output_text.strip()

    raise ValueError(f"Unsupported setter model: {setter_model}")

def create_hidden_chain_with_llm(board_words, strategy_notes = "",
                                 setter_model = MODEL, use_thinking = False):
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
            response_text = get_text_response_from_setter_model(
                setter_model,
                system_prompt,
                current_prompt,
                max_output_tokens = 1600,
                use_thinking = use_thinking
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

def update_setter_strategy_notes(current_strategy_notes, paired_game_summaries,
                                 setter_model = MODEL):
    system_prompt = """
    You improve the strategy notes of a setter in a word-association game.
    The setter builds chains on a new random board every game, so the notes
    must help on boards it has never seen.

    Review the paired guesser's game outcomes, including what it guessed
    instead at each missed link and why.

    Guidelines:
    - Base every lesson on the game evidence provided. Do not claim a link
      caused a failure unless the evidence supports that conclusion.
    - A completed chain shows what may work, and a failed chain shows what
      to investigate. Neither proves every link in it was strong or weak.
    - Look closely at missed links. When the guesser picked another word,
      consider why that word seemed like a better fit.
    - Distinguish links that were attempted and missed from links
      the guesser never reached.
    - Do not treat an unreached link as evidence that the association
      itself was difficult.
    - Distinguish a reasonable alternative guess from evidence that
      the intended association was genuinely ambiguous.
    - Write general principles, not lists of past chains. Use at most two
      short examples, only when they clarify a principle.
    - Keep useful existing notes and refine them. Mark lessons drawn from
      a single game as tentative.
    - Prefer common, direct, unambiguous associations.
    - Keep the notes to 150 words or fewer.

    Return only valid JSON with exactly this field:
    {
        "updated_strategy_notes": "Your revised strategy notes"
    }
    """

    user_prompt = f"""
    Current strategy notes:
    {current_strategy_notes or "No strategy notes yet."}

    Paired guesser game summaries:
    {json.dumps(paired_game_summaries, indent=2)}

    Update the strategy notes based on this evidence.
    Return only the required JSON object.
    """

    try:
        response_text = get_text_response_from_setter_model(
            setter_model,
            system_prompt,
            user_prompt,
            max_output_tokens = 700
        )

        # Remove Markdown code fences if the model includes them.
        if response_text.startswith("```"):
            lines = response_text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            response_text = "\n".join(lines).strip()

        # parse first JSON object in the response
        decoder = json.JSONDecoder()
        data, end_position = decoder.raw_decode(response_text)

        if not isinstance(data, dict):
            raise ValueError("Reflection response must be a JSON object.")

        updated_notes = data.get("updated_strategy_notes")

        if not isinstance(updated_notes, str) or not updated_notes.strip():
            raise ValueError(
                "Reflection returned empty or invalid strategy notes."
            )

        updated_notes = updated_notes.strip()

        if len(updated_notes.split()) > 150:
            raise ValueError(
                "Reflection exceeded the 150-word limit."
            )

        return updated_notes

    except Exception as error:
        print(f"Strategy reflection failed: {error}")
        print("Keeping the previous strategy notes.")
        return current_strategy_notes

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