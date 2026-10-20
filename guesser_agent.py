from dotenv import load_dotenv
from anthropic import Anthropic
import os
import json

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def choose_next_word_with_llm(board_words, current_clue, used_words,
                              wrong_guesses, lives_remaining):
    available_words = []
    for word in board_words:
        if word not in used_words and word not in wrong_guesses:
            available_words.append(word)

    system_prompt = """You are playing a word association game called CONNECTION.

    Your goal is to identify the single board word most directly associated
    with the current clue.

    Rules:
    1. You may choose ONLY from the available words provided by the user.
    2. Choose the word with the strongest, most natural, and most direct
    connection to the current clue.
    3. Prefer common, widely understood associations over obscure, indirect,
    historical, mythological, or speculative connections.
    4. Do not invent a connection just to justify a weak candidate.
    5. Consider how naturally a person would make the association without
    needing a long explanation.
    6. Do not choose a word that has already been guessed.
    7. If multiple words seem plausible, choose the strongest association,
    not simply a word that can be connected through an elaborate story.
    8. Return ONLY valid JSON. Do not use Markdown fences or add commentary.

    Your response must have exactly these two fields:
    {
        "chosen_word": "ONE AVAILABLE WORD",
        "reason_for_connection": "A brief explanation of the connection"
    }"""

    user_prompt = f"""Current clue: {current_clue}

    Available words: {available_words}

    Lives remaining: {lives_remaining}

    Choose the single available word with the strongest direct association
    with the current clue. Keep your reasoning brief and grounded in a
    natural, commonly understood connection.

    Return only the required JSON."""
    
    response = client.messages.create(
        model = "claude-haiku-5-5",
        max_tokens = 1024,
        system = system_prompt,
        messages = [
            {"role": "user", "content": user_prompt}
        ]
    )
    print("STOP REASON:", response.stop_reason)
    print("OUTPUT TOKENS:", response.usage.output_tokens)
    text_blocks = [block for block in response.content if block.type == "text"]
    response_text = text_blocks[0].text if text_blocks else ""
    print("RAW CLAUDE RESPONSE:", repr(response_text))
    
    try:
        parsed_response = json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "chosen_word": None,
            "reason_for_connection": "Parsing of the response failed."
        }

    if "chosen_word" not in parsed_response or "reason_for_connection" not in parsed_response:
        return {
            "chosen_word": None,
            "reason_for_connection": "Claude's response is missing a required field."
        }
    
    chosen_word = parsed_response["chosen_word"]

    if not isinstance(chosen_word, str):
        return {
            "chosen_word": None,
            "reason_for_connection": "Claude returned an invalid word."
        }

    chosen_word = chosen_word.upper()

    if chosen_word not in [word.upper() for word in available_words]:
        return {
            "chosen_word": None,
            "reason_for_connection": "Claude selected a word that is not available."
        }
    reason_for_connection = parsed_response["reason_for_connection"]
    if not isinstance(reason_for_connection, str):
        return {
            "chosen_word": None,
            "reason_for_connection": "Claude returned an invalid explanation."
        }
    
    return {"chosen_word": chosen_word, "reason_for_connection": reason_for_connection}

