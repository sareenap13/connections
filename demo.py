"""Builds demo.html from the experiment logs.
"""
import html
import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone

GAME_LOG_FILE = "game_logs.jsonl"
STRATEGY_NOTES_FILE = "strategy_notes_history.jsonl"
OUTPUT_PAGE_FILE = "demo.html"
REPO_URL = "github.com/sareenap13/connections"

RUN_IDS = {
    "haiku_setter_no_thinking": "20261020T155229036857Z",
    "gpt_setter": "20261021T024629148670Z",
    "haiku_setter_with_thinking": "20261021T124858700832Z",
}
SETTER_LABELS = {
    "haiku_setter_no_thinking": "Haiku setter, thinking off",
    "haiku_setter_with_thinking": "Haiku setter, thinking on",
    "gpt_setter": "GPT-5-mini setter",
}
KNIGHT_EXAMPLE_RUN_ID = "20261021T124527751245Z"
KNIGHT_EXAMPLE_GAME_NUMBER = 1
MARIO_CHAIN = ["PRINCESS", "PEACH", "CASTLE", "STAR", "MOON"]
BACKUP_REPLAY_CHAIN = ["TEQUILA", "SALT", "LEMON", "ORANGE", "PEACH"]
QUOTE_SEARCH_TERMS = ["EVEREST->HORSE was a missed", "cookie-cutter robot"]

WEAK_LINK_ADMISSION_PATTERN = re.compile(
    r"weak|loose|tenuous|revise|reconsider|not ideal|better chain|unclear|unrelated",
    re.IGNORECASE,
)
CORRECT_OUTCOMES = ("correct", "chain_complete")

ISOLATION_CODE_EXCERPT = '''# run_self_play_batches.py
if guesser_role == "paired":
    paired_feedback_games.append(record)

# summarize_paired_games()
if game.get("guesser_role") != "paired":
    continue   # the held-out guesser never reaches reflection'''

THINKING_CODE_EXCERPT = '''# setter_agent.py  (the whole change)

# run 1
thinking={"type": "disabled"}

# run 3
thinking={"type": "adaptive"},
extra_body={"output_config":
            {"effort": "medium"}}'''


# ---------- data ----------

def load_jsonl_records(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def count_links_found(game_record):
    return sum(move.get("outcome") in CORRECT_OUTCOMES for move in game_record.get("moves") or [])


def guesser_family(game_record):
    return "haiku" if game_record["guesser_model"].startswith("claude") else "gpt"


def setter_admitted_a_weak_link(game_record):
    return any(WEAK_LINK_ADMISSION_PATTERN.search(reason) for reason in game_record.get("setter_reasons") or [])


def played_games_for_run(all_game_records, run_id):
    return [g for g in all_game_records if g.get("run_id") == run_id and g.get("status") == "played"]


def average(values):
    return statistics.mean(values) if values else 0.0


def run_start_time(run_id):
    return datetime.strptime(run_id, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)


def strategy_notes_for_run(all_strategy_notes, run_id):
    run_start = run_start_time(run_id)
    later_starts = sorted(run_start_time(r) for r in RUN_IDS.values() if run_start_time(r) > run_start)
    next_start = later_starts[0] if later_starts else None
    notes = [
        note for note in all_strategy_notes
        if datetime.fromisoformat(note["timestamp"]) >= run_start
        and (next_start is None or datetime.fromisoformat(note["timestamp"]) < next_start)
    ]
    return sorted(notes, key=lambda note: note["strategy_notes_version"])


def same_model_edge_for_run(all_game_records, run_id):
    links_by_game = defaultdict(dict)
    for game in played_games_for_run(all_game_records, run_id):
        links_by_game[(game["batch_number"], game["game_number"])][guesser_family(game)] = count_links_found(game)
    matched = [links for links in links_by_game.values() if len(links) == 2]
    return {
        "chains": len(matched),
        "haiku": average([links["haiku"] for links in matched]),
        "gpt": average([links["gpt"] for links in matched]),
    }


def first_game_pair_with_chain(all_game_records, run_ids, chain):
    matching = [g for g in all_game_records
                if g.get("run_id") in run_ids and g.get("status") == "played" and g.get("hidden_chain") == chain]
    if not matching:
        return []
    first_key = min((g["run_id"], g["batch_number"], g["game_number"]) for g in matching)
    pair = [g for g in matching if (g["run_id"], g["batch_number"], g["game_number"]) == first_key]
    return sorted(pair, key=lambda g: g["guesser_role"] != "paired")


# ---------- html helpers ----------

def escape(text):
    return html.escape(str(text))


def short_model_name(model):
    return "Haiku" if model.startswith("claude") else "GPT-5-mini"


def bar_row(label, value, maximum, color_class, value_text=None):
    width_percent = 0 if maximum == 0 else 100 * value / maximum
    return (f'<div class="bar-row"><span class="bar-label">{escape(label)}</span>'
            f'<span class="bar-track"><span class="bar {color_class}" style="width:{width_percent:.1f}%"></span></span>'
            f'<span class="bar-value">{escape(value_text or f"{value:.2f}")}</span></div>')


def move_line(move):
    is_correct = move["outcome"] in CORRECT_OUTCOMES
    mark = '<span class="ok">✓</span>' if is_correct else '<span class="no">✗</span>'
    return f'<div class="move">{escape(move["clue"])} → <b>{escape(move["chosen_word"])}</b> {mark}</div>'


def section(section_id, kicker, title, body, takeaway=None):
    takeaway_html = f'<p class="takeaway">{escape(takeaway)}</p>' if takeaway else ""
    return (f'<section id="{section_id}"><div class="inner">'
            f'<div class="kicker">{escape(kicker)}</div>' + (f'<h2>{escape(title)}</h2>' if title else '') +
            f'{body}{takeaway_html}</div></section>')


# ---------- sections ----------

def build_hook_section(all_game_records):
    pair = [g for g in all_game_records
            if g.get("run_id") == KNIGHT_EXAMPLE_RUN_ID and g.get("game_number") == KNIGHT_EXAMPLE_GAME_NUMBER
            and g.get("status") == "played"]
    pair = sorted(pair, key=lambda g: g["guesser_role"] != "paired")
    board_tiles = "".join(f'<div class="tile">{escape(w)}</div>' for w in pair[0]["board_words"])
    guess_columns = ""
    for game in pair:
        moves = "".join(move_line(m) for m in game["moves"] if m["clue"] == "KNIGHT" and m.get("chosen_word"))
        guess_columns += f'<div class="guess-col"><h3>{short_model_name(game["guesser_model"])}</h3>{moves}</div>'
    body = (f'<div class="board">{board_tiles}</div>'
            f'<p class="clue">Clue <span>KNIGHT</span>. Which word comes next?</p>'
            f'<button class="reveal-button" data-target="knight-reveal">Reveal what the agents guessed</button>'
            f'<div id="knight-reveal" class="hidden"><div class="guess-grid">{guess_columns}</div>'
            f'<p class="chain">{" → ".join(escape(w) for w in pair[0]["hidden_chain"])}</p></div>')
    return section("hook", "CONNECTION · harder one", "Now try this", body)


def build_loop_section():
    body = ('<div class="loop">'
            '<div class="node setter">Setter builds a chain<br><small>random 16-word board</small></div>'
            '<div class="branches">'
            '<div class="branch"><div class="node paired">Same-model guesser</div>'
            '<div class="arrow">→</div><div class="node notes">Setter rewrites its strategy notes</div></div>'
            '<div class="branch"><div class="node heldout">Other-model guesser</div>'
            '<div class="arrow">→</div><div class="node blind">Logged, but kept out of reflection</div></div>'
            '</div></div>'
            f'<pre><code>{escape(ISOLATION_CODE_EXCERPT)}</code></pre>')
    return section("loop", "What I built", "A loop with a held-out guesser", body,
                   "The loop learns from one guesser. The other one tests what it produces.")


def build_run_one_section(all_game_records, all_strategy_notes):
    run_id = RUN_IDS["haiku_setter_no_thinking"]
    played = played_games_for_run(all_game_records, run_id)
    batches = sorted({g["batch_number"] for g in played})
    columns = ""
    for batch in batches:
        same = average([count_links_found(g) for g in played if g["batch_number"] == batch and guesser_family(g) == "haiku"])
        other = average([count_links_found(g) for g in played if g["batch_number"] == batch and guesser_family(g) == "gpt"])
        columns += (f'<div class="col-group"><div class="cols">'
                    f'<span class="col c-haiku" style="height:{same / 4 * 100:.0f}%" title="{same:.2f}"></span>'
                    f'<span class="col c-gpt" style="height:{other / 4 * 100:.0f}%" title="{other:.2f}"></span>'
                    f'</div><span class="col-label">{batch}</span></div>')
    rows = (f'<div class="legend"><span class="key c-haiku"></span>same-model guesser'
            f'<span class="key c-gpt"></span>other-model guesser</div>'
            f'<div class="column-chart"><div class="axis"><span>4</span><span>2</span><span>0</span></div>{columns}</div>'
            f'<div class="col-caption">batch</div>')
    notes = strategy_notes_for_run(all_strategy_notes, run_id)
    body = (f'<p class="sub">Average links found per game (out of 4), batch by batch. Haiku setter, thinking off.</p>'
            f'{rows}'
            f'<p class="sub">Strategy notes v{notes[0]["strategy_notes_version"]} had {len(notes[0]["strategy_notes"].split())} words. '
            f'v{notes[-1]["strategy_notes_version"]} had {len(notes[-1]["strategy_notes"].split())}, with more specific rules each round.</p>')
    return section("run-one", "Run 1 · 99 chains, 10 rounds of reflection", "The notes kept changing", body,
                   "The scores didn't.")


def build_quotes_section(all_game_records):
    run_id = RUN_IDS["haiku_setter_no_thinking"]
    paired = [g for g in played_games_for_run(all_game_records, run_id) if g["guesser_role"] == "paired"]
    quotes_html = ""
    raw_record_html = ""
    for term in QUOTE_SEARCH_TERMS:
        for game in paired:
            matches = [r for r in game["setter_reasons"] if term in r]
            if matches:
                quotes_html += (f'<blockquote>“{escape(matches[0])}”'
                                f'<cite>Shipped chain: {" → ".join(escape(w) for w in game["hidden_chain"])}</cite></blockquote>')
                if not raw_record_html:
                    excerpt = {"batch_number": game["batch_number"], "hidden_chain": game["hidden_chain"],
                               "setter_reasons": game["setter_reasons"]}
                    raw_record_html = (f'<details><summary>Raw log record</summary>'
                                       f'<pre><code>{escape(json.dumps(excerpt, indent=2))}</code></pre></details>')
                break
    batches = sorted({g["batch_number"] for g in paired})
    admissions = [sum(setter_admitted_a_weak_link(g) for g in paired if g["batch_number"] == b) for b in batches]
    admission_bars = "".join(
        f'<div class="mini"><span class="mini-bar" style="height:{count * 10}%"></span><span>{count}</span></div>'
        for count in admissions)
    body = (f'{quotes_html}{raw_record_html}'
            f'<p class="sub">Chains per batch of 10 where the setter called its own link weak</p>'
            f'<div class="minis">{admission_bars}</div>')
    return section("quotes", "Run 1", "In its own words", body, "It could see the weakness. It shipped the chain anyway.")


def build_flag_section(all_game_records):
    summaries = {}
    for key, run_id in RUN_IDS.items():
        played = played_games_for_run(all_game_records, run_id)
        paired = [g for g in played if g["guesser_role"] == "paired"]
        summaries[key] = {
            "links": average([count_links_found(g) for g in played]),
            "weak": 100 * average([setter_admitted_a_weak_link(g) for g in paired]),
            "chains": len(paired),
        }
    order = ["haiku_setter_no_thinking", "haiku_setter_with_thinking", "gpt_setter"]
    link_bars = "".join(bar_row(f'{SETTER_LABELS[k]} ({summaries[k]["chains"]})', summaries[k]["links"], 4,
                                "c-haiku" if "haiku" in k else "c-gpt") for k in order)
    weak_bars = "".join(bar_row(SETTER_LABELS[k], summaries[k]["weak"], 100, "c-warn",
                                f'{summaries[k]["weak"]:.0f}%') for k in order)
    body = (f'<div class="two-col"><pre><code>{escape(THINKING_CODE_EXCERPT)}</code></pre>'
            f'<div><h3>Links found per game</h3>{link_bars}'
            f'<h3>Chains where the setter called its own link weak</h3>{weak_bars}</div></div>')
    return section("flag", "Control runs", "One config flag", body,
                   "One setting did more than ten rounds of reflection. Separate runs, so a strong hint, not proof.")


def build_same_model_section(all_game_records):
    order = ["haiku_setter_no_thinking", "haiku_setter_with_thinking", "gpt_setter"]
    groups = ""
    for key in order:
        edge = same_model_edge_for_run(all_game_records, RUN_IDS[key])
        difference = edge["haiku"] - edge["gpt"]
        groups += (f'<div class="group"><h3>{SETTER_LABELS[key]} <small>{edge["chains"]} chains</small></h3>'
                   f'{bar_row("Haiku", edge["haiku"], 4, "c-haiku")}'
                   f'{bar_row("GPT", edge["gpt"], 4, "c-gpt")}'
                   f'<p class="edge">Haiku edge {difference:+.2f}</p></div>')
    mario_pair = first_game_pair_with_chain(all_game_records, [RUN_IDS["haiku_setter_with_thinking"]], MARIO_CHAIN)
    mario_html = ""
    if mario_pair:
        lines = "".join(f'<div>{short_model_name(g["guesser_model"])} found <b>{count_links_found(g)}</b> of 4</div>'
                        for g in mario_pair)
        mario_html = f'<div class="example"><p class="chain">{" → ".join(MARIO_CHAIN)}</p>{lines}</div>'
    body = f'<div class="groups">{groups}</div>{mario_html}'
    return section("same-model", "Who reads whose chains · links found by each guesser", "Haiku reads Haiku better", body,
                   "The same model is the easiest audience. Test with a different one.")


def build_takeaways_section(all_game_records):
    def average_links_for_run(run_key):
        return average([count_links_found(g) for g in played_games_for_run(all_game_records, RUN_IDS[run_key])])
    links_without_thinking = average_links_for_run("haiku_setter_no_thinking")
    links_with_thinking = average_links_for_run("haiku_setter_with_thinking")
    edge_without_thinking = same_model_edge_for_run(all_game_records, RUN_IDS["haiku_setter_no_thinking"])
    edge_with_thinking = same_model_edge_for_run(all_game_records, RUN_IDS["haiku_setter_with_thinking"])
    evidence_rows = [
        ("Reflecting on its own notes", "10 rounds", "flat"),
        ("Room to think", f"{links_without_thinking:.2f} → {links_with_thinking:.2f}", "links found"),
        ("Same model as guesser", f"+{edge_without_thinking['haiku'] - edge_without_thinking['gpt']:.2f} / "
                             f"+{edge_with_thinking['haiku'] - edge_with_thinking['gpt']:.2f}", "same-model edge"),
    ]
    evidence_html = "".join(
        f'<div class="evidence"><span class="evidence-label">{escape(label)}</span>'
        f'<span class="evidence-value">{escape(value)}</span><span class="evidence-unit">{escape(unit)}</span></div>'
        for label, value, unit in evidence_rows)
    body = ('<p class="answer">Not from its own notes.<br>'
            '<span>It got better when it had room to think.</span><br>'
            'And its own model followed it better than another model did.</p>'
            f'<div class="evidence-grid">{evidence_html}</div>'
            '<div class="lessons-row">'
            '<div><b>1</b>Check the cheap settings first</div>'
            '<div><b>2</b>Test with a different model</div>'
            '<div><b>3</b>Run the control that could prove you wrong</div>'
            '</div>'
            f'<p class="closing"><span class="repo">{escape(REPO_URL)}</span>'
            '<span class="sub">One run per condition. 99, 60 and 37 matched chains.</span></p>')
    return section("takeaways", "So, can an AI agent learn to make better decisions?", "", body)


def build_title_section():
    return ('<section id="title" class="title-section"><div class="inner">'
            '<div class="title-name">CONNECTION</div>'
            '<h1 class="title-question">Can an AI agent learn to make better decisions?</h1>'
            '<p class="title-byline">Sareena Parikh · AI Tinkerers NYC · Agentic Loops Demo Day</p>'
            '</div></section>')


def build_backup_section(all_game_records):
    pair = first_game_pair_with_chain(all_game_records, list(RUN_IDS.values()), BACKUP_REPLAY_CHAIN)
    if not pair:
        return ""
    game = pair[0]
    tiles = "".join(f'<button class="tile play-tile" data-word="{escape(w)}">{escape(w)}</button>'
                    for w in game["board_words"])
    agent_columns = ""
    for agent_game in pair:
        moves = "".join(move_line(m) for m in agent_game["moves"] if m.get("chosen_word"))
        agent_columns += (f'<div class="guess-col"><h3>{short_model_name(agent_game["guesser_model"])} '
                          f'<small>found {count_links_found(agent_game)} of 4</small></h3>{moves}</div>')
    body = (f'<div id="play-game" data-chain="{escape(json.dumps(game["hidden_chain"]))}">'
            f'<div class="play-status"><p class="clue">Clue <span id="play-clue">{escape(game["hidden_chain"][0])}</span></p>'
            f'<p class="lives">Lives <span id="play-lives">♥ ♥ ♥</span></p></div>'
            f'<div class="board">{tiles}</div>'
            f'<p id="play-message" class="play-message">Find the next word. Each correct word becomes the new clue.</p>'
            f'<button class="reveal-button" data-target="agents-played">Show how the agents played this chain</button>'
            f'<div id="agents-played" class="hidden"><div class="guess-grid">{agent_columns}</div>'
            f'<p class="chain">{" → ".join(escape(w) for w in game["hidden_chain"])}</p></div></div>')
    return section("backup", "CONNECTION · you are the guesser", "Your turn", body)


PAGE_STYLE = """
:root{--bg:#0f1115;--panel:#181b22;--ink:#f2f3f5;--muted:#9aa3b2;--line:#2a2f3a;
--haiku:#d97757;--gpt:#6aa9ff;--warn:#e8b04b;--ok:#4cc38a;--no:#ef6a6a}
*{box-sizing:border-box}html{scroll-snap-type:y mandatory;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:22px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
section{min-height:100vh;scroll-snap-align:start;display:flex;align-items:center;border-bottom:1px solid var(--line)}
.inner{width:100%;max-width:1200px;margin:0 auto;padding:56px 48px}
.kicker{color:var(--muted);font-size:18px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px}
h2{font-size:56px;line-height:1.1;margin:0 0 28px}h3{font-size:22px;margin:22px 0 10px;color:var(--muted);font-weight:600}
h3 small{font-weight:400;display:block;font-size:18px}.sub{color:var(--muted);font-size:20px}
.takeaway{font-size:34px;font-weight:700;margin-top:32px;border-left:6px solid var(--warn);padding-left:20px}
.board{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;max-width:900px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 10px;text-align:center;font-weight:700;font-size:24px;letter-spacing:.04em}
.clue{font-size:30px;margin:26px 0}.clue span{color:var(--warn);font-weight:800}
.reveal-button{font:inherit;font-size:20px;background:var(--panel);color:var(--ink);border:1px solid var(--muted);border-radius:8px;padding:10px 18px;cursor:pointer}
.hidden{display:none}.guess-grid{display:flex;gap:64px;margin-top:20px}.guess-col h3{margin-top:0}
.move{font-size:30px;margin:6px 0}.ok{color:var(--ok)}.no{color:var(--no)}
.chain{font-size:30px;font-weight:700;margin-top:22px;letter-spacing:.02em}
pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px;font-size:19px;line-height:1.5;overflow:auto;margin:0}
code{font-family:"SF Mono",Menlo,Consolas,monospace}
.loop{display:flex;align-items:center;gap:28px;margin-bottom:28px}.branches{display:flex;flex-direction:column;gap:18px}
.branch{display:flex;align-items:center;gap:14px}.arrow{color:var(--muted);font-size:30px}
.node{background:var(--panel);border:2px solid var(--line);border-radius:10px;padding:14px 18px;font-weight:600}
.node small{color:var(--muted);font-weight:400}.paired{border-color:var(--haiku)}.heldout{border-color:var(--gpt)}.blind{color:var(--muted);border-style:dashed}
.bar-row{display:grid;grid-template-columns:340px 1fr 80px;align-items:center;gap:14px;margin:8px 0}
.bar-label{color:var(--muted);font-size:20px}.bar-track{background:var(--panel);border-radius:6px;height:26px;overflow:hidden}
.bar{display:block;height:100%;border-radius:6px}.bar-value{font-weight:700;text-align:right}
.c-haiku{background:var(--haiku)}.c-gpt{background:var(--gpt)}.c-warn{background:var(--warn)}
.batch-row{display:grid;grid-template-columns:110px 1fr;align-items:center;gap:10px}
.batch-row .bar-row{grid-template-columns:150px 1fr 70px;margin:2px 0}.batch-row .bar-track{height:14px}.batch-row .bar-label{font-size:16px}
.batch-label{color:var(--muted);font-size:18px}.batches{margin:10px 0 18px}
blockquote{font-size:32px;line-height:1.35;margin:0 0 26px;padding-left:22px;border-left:4px solid var(--haiku)}
cite{display:block;font-style:normal;color:var(--muted);font-size:20px;margin-top:8px}
details{margin:0 0 20px}summary{cursor:pointer;color:var(--muted);font-size:20px;margin-bottom:10px}
.minis{display:flex;gap:18px;align-items:flex-end;height:150px;margin-top:10px}
.mini{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;width:44px;font-weight:700}
.mini-bar{width:100%;background:var(--warn);border-radius:4px 4px 0 0;margin-bottom:6px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}
.two-col .bar-row{grid-template-columns:300px 1fr 70px}
.groups{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}.group .bar-row{grid-template-columns:130px 1fr 60px}
.edge{font-size:24px;font-weight:700;color:var(--warn)}.example{margin-top:22px;font-size:24px}
.lessons{font-size:36px;line-height:1.4;padding-left:40px}.lessons li{margin:14px 0}.repo{font-size:24px;color:var(--warn)}
.moves .move{font-size:26px}
.play-tile{font:inherit;font-weight:700;font-size:24px;color:var(--ink);cursor:pointer;transition:transform .08s,background .2s}
.play-tile:hover:not(:disabled){border-color:var(--warn);transform:translateY(-2px)}
.play-tile:disabled{cursor:default}
.play-tile.found{background:#173a2a;border-color:var(--ok);color:var(--ok)}
.play-tile.missed{background:#3a1a1c;border-color:var(--no);color:var(--no);opacity:.7}
.play-tile.answer{border-color:var(--warn);color:var(--warn)}
.play-status{display:flex;gap:56px;align-items:baseline}.play-status .clue{margin:0 0 18px}
.lives{font-size:26px;color:var(--muted)}.lives span{color:var(--no);letter-spacing:.15em}
.play-message{font-size:28px;font-weight:600;min-height:40px;margin:22px 0}
#agents-played .guess-grid{margin-top:4px;flex-direction:column;gap:10px}#agents-played .guess-col{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 22px}#agents-played .guess-col h3{margin:0;min-width:200px}#agents-played .move{font-size:22px;margin:0}#agents-played .chain{font-size:24px;margin-top:12px}

.legend{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:18px;margin:6px 0 14px}
.key{display:inline-block;width:18px;height:18px;border-radius:4px;margin-left:14px}.legend .key:first-child{margin-left:0}
.column-chart{display:flex;align-items:flex-end;gap:22px;height:300px;border-bottom:1px solid var(--line);padding-left:6px}
.axis{display:flex;flex-direction:column;justify-content:space-between;height:100%;color:var(--muted);font-size:16px;margin-right:8px}
.col-group{display:flex;flex-direction:column;align-items:center;height:100%;flex:1}
.cols{display:flex;align-items:flex-end;gap:4px;height:100%;width:100%;justify-content:center}
.col{display:block;width:40%;border-radius:4px 4px 0 0}
.col-label{color:var(--muted);font-size:18px;margin-top:6px;position:relative;top:30px}
.col-caption{color:var(--muted);font-size:16px;text-align:center;margin-top:34px}
blockquote{font-size:28px}
.group .bar-row{grid-template-columns:70px 1fr 60px}
section{padding:10px 0}
.title-name{font-size:30px;font-weight:800;letter-spacing:.28em;color:var(--warn);margin-bottom:22px}
.title-question{font-size:72px;line-height:1.08;margin:0 0 36px;max-width:1050px}
.title-byline{font-size:22px;color:var(--muted)}
#takeaways .kicker{font-size:22px;color:var(--warn);letter-spacing:.06em;text-transform:none;margin-bottom:18px}
.answer{font-size:46px;line-height:1.18;font-weight:800;margin:0 0 36px}.answer span{color:var(--ok)}
.evidence-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-bottom:30px}
.evidence{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 22px;display:flex;flex-direction:column}
.evidence-label{color:var(--muted);font-size:19px}.evidence-value{font-size:36px;font-weight:800;margin:4px 0}.evidence-unit{color:var(--muted);font-size:17px}
.lessons-row{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;font-size:23px;font-weight:600}
.lessons-row b{display:block;color:var(--warn);font-size:20px;margin-bottom:4px}
.closing{display:flex;justify-content:space-between;align-items:baseline;margin-top:34px;gap:20px}
#fullscreen-button{position:fixed;top:18px;right:22px;z-index:10;font:inherit;font-size:16px;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 14px;cursor:pointer;opacity:.75}
#fullscreen-button:hover{opacity:1;color:var(--ink)}
:fullscreen #fullscreen-button{display:none}
@media (max-width:900px){.two-col,.groups{grid-template-columns:1fr}.bar-row{grid-template-columns:160px 1fr 60px}h2{font-size:40px}}
"""

PAGE_SCRIPT = """
const sections=[...document.querySelectorAll('section')];
function currentIndex(){let best=0,dist=1e9;sections.forEach((s,i)=>{const d=Math.abs(s.getBoundingClientRect().top);if(d<dist){dist=d;best=i}});return best}
function go(i){const s=sections[Math.max(0,Math.min(sections.length-1,i))];s.scrollIntoView()}
function revealIn(section){const b=section.querySelector('.reveal-button');if(b){b.click()}}
document.querySelectorAll('.reveal-button').forEach(b=>b.addEventListener('click',()=>{
  document.getElementById(b.dataset.target).classList.remove('hidden');b.style.display='none'}));
document.addEventListener('keydown',e=>{
  if(e.key===' '||e.key==='ArrowDown'||e.key==='PageDown'){e.preventDefault();go(currentIndex()+1)}
  else if(e.key==='ArrowUp'||e.key==='PageUp'){e.preventDefault();go(currentIndex()-1)}
  else if(e.key==='r'||e.key==='R'){revealIn(sections[currentIndex()])}
  else if(e.key==='f'||e.key==='F'){toggleFullscreen()}});
function toggleFullscreen(){
  if(document.fullscreenElement){document.exitFullscreen()}else{document.documentElement.requestFullscreen()}}
document.getElementById('fullscreen-button').addEventListener('click',toggleFullscreen);

const playGame=document.getElementById('play-game');
if(playGame){
  const hiddenChain=JSON.parse(playGame.dataset.chain);
  let chainPosition=0, livesRemaining=3, gameIsOver=false;
  const clueLabel=document.getElementById('play-clue');
  const livesLabel=document.getElementById('play-lives');
  const message=document.getElementById('play-message');
  const tiles=[...playGame.querySelectorAll('.play-tile')];
  function showLives(){livesLabel.textContent=livesRemaining>0?Array(livesRemaining).fill('♥').join(' '):'none left'}
  function endGame(text){
    gameIsOver=true;message.textContent=text;
    tiles.forEach(t=>{t.disabled=true;if(hiddenChain.slice(chainPosition+1).includes(t.dataset.word)){t.classList.add('answer')}})}
  tiles.forEach(tile=>tile.addEventListener('click',()=>{
    if(gameIsOver||tile.disabled)return;
    const guessedWord=tile.dataset.word, intendedWord=hiddenChain[chainPosition+1];
    tile.disabled=true;
    if(guessedWord===intendedWord){
      tile.classList.add('found');chainPosition+=1;
      if(chainPosition===hiddenChain.length-1){endGame('You found the chain. Now see how two models solved it.');return}
      clueLabel.textContent=guessedWord;message.textContent='Correct. '+guessedWord+' is your new clue.';
    }else{
      tile.classList.add('missed');livesRemaining-=1;showLives();
      if(livesRemaining===0){endGame('Out of lives. You found '+chainPosition+' of 4 links. Answers in gold.');return}
      message.textContent='Not that one. Try again.';
    }}));
}
"""


def main():
    all_game_records = load_jsonl_records(GAME_LOG_FILE)
    all_strategy_notes = load_jsonl_records(STRATEGY_NOTES_FILE)
    sections_html = "".join([
        build_title_section(),
        build_backup_section(all_game_records),
        build_hook_section(all_game_records),
        build_loop_section(),
        build_run_one_section(all_game_records, all_strategy_notes),
        build_quotes_section(all_game_records),
        build_flag_section(all_game_records),
        build_same_model_section(all_game_records),
        build_takeaways_section(all_game_records),
    ])
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Did My Agents Get Better?</title><style>{PAGE_STYLE}</style></head>'
            f'<body><button id="fullscreen-button" title="Full screen (F)">⛶ Full screen</button>{sections_html}<script>{PAGE_SCRIPT}</script></body></html>')
    with open(OUTPUT_PAGE_FILE, "w", encoding="utf-8") as file:
        file.write(page)
    print(f"Wrote {OUTPUT_PAGE_FILE}")


if __name__ == "__main__":
    main()