"""OpenAI tool-calling loop, streamed: turns a natural-language question about
the DISCOM data into one or more structured tool calls (app.chatbot.tools),
then streams the model's final explanation token-by-token. Yields a sequence
of event dicts consumed by the SSE endpoint in routers/chat.py:
  {"type": "tool_result", "tool": str, "chart": dict|None}
  {"type": "token", "text": str}
  {"type": "done", "answer": str, "charts": [dict, ...]}
"""
import json
from typing import Iterator

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.chatbot.tools import TOOLS, dispatch

SYSTEM_PROMPT_TEMPLATE = """You are Sarthi, a data analyst assistant for an Indian power \
distribution company (DISCOM). If the user only greets you (e.g. "hi", "hello", \
"hey") without asking anything, reply with exactly: "Hi, my name is Sarthi. How \
can I help you today?" -- nothing more. You answer questions about two datasets:

1. Transformer/distribution losses -- REAL production data (monthly DT-level \
energy audit reports, covering {loss_date_range}): Date, Division, Substation_Names, \
Feeder_Name, Transformer_ID, DT_type, Feeder_Type, Area_Type, Consumer_Count, \
Energy_Input_kWh, Energy_Billed_kWh, Units_Loss_kWh, Distribution_Loss_Pct, \
Data_Quality_Flag ('Outlier' rows with implausible % from near-zero readings \
are already excluded from aggregate tools). Divisions: {divisions}. Network \
hierarchy, broadest to narrowest: Division > Substation (Substation_Names) > \
Feeder (Feeder_Name) > Transformer (Transformer_ID).
2. Theft case booking history -- SYNTHETIC PLACEHOLDER data (not real; \
generated pending a real dataset), sampled onto real feeder/division names, \
covering {theft_date_range}: Case_ID, Date, Division, Feeder_Name, Area_Type, \
Theft_Type, Units_Stolen_kWh, Fine_Amount_INR, Case_Status, FIR_Filed.

If asked about the date range or coverage of the data, use the ranges stated \
above -- do not guess or recall a different range from earlier in the \
conversation, since the underlying files can be updated between sessions.

Always answer using the provided tools -- never guess numbers. Call one or \
more tools to gather the data needed, then write a concise, specific answer \
that cites the actual figures returned (percentages, counts, amounts in INR). \
Whenever your answer relies on theft-case figures, clearly note that theft \
data is synthetic/placeholder, not real. If a chart was generated, briefly \
reference what it shows but do not describe it as an image; the chart is \
rendered separately in the UI. Keep answers to 2-5 sentences unless the \
question calls for a longer breakdown.

IMPORTANT -- match the tool to the aggregation level the question actually \
asks about, and never state a number at one level (a single transformer, \
feeder, or substation) as if it were the value for a broader group (its \
substation, its division, its DT type, the whole network) -- these are all \
different levels of the Division > Substation > Feeder > Transformer \
hierarchy and their averages differ. If asked about a Division, call \
get_loss_by_division; about a Substation, call get_top_loss_substations or \
filter by substation_name; about a transformer type, call get_loss_by_dt_type; \
about a specific feeder, call get_top_loss_feeders or filter by feeder_name. \
If unsure, call more than one tool rather than repurpose a result from the \
wrong level.
"""

UPLOADED_DOCS_SYSTEM_TEMPLATE = """The user has attached the following document(s) to this \
conversation (CSV/Excel/Word/PowerPoint). Their content -- or a bounded preview, marked \
"truncated" below if the full document didn't fit -- is included here. Answer questions \
about these documents directly from this content; don't use the DISCOM analytics tools \
for them, and don't mix their content up with the DISCOM loss/theft datasets. For a \
truncated spreadsheet, the numeric summary and row preview may not cover the whole file --\
say so rather than presenting a preview-based figure as an exact total. If a question \
isn't answerable from what's shown, say so rather than guessing.

{context}
"""

MAX_TOOL_ROUNDS = 4


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to backend/.env or the project .env and restart the server."
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def _date_range_str(df) -> str:
    if df.empty:
        return "no data"
    return f"{df['Date'].min().strftime('%b %Y')} to {df['Date'].max().strftime('%b %Y')}"


def _build_system_prompt(losses, theft) -> str:
    # Derived from the actual loaded data on every request rather than
    # hardcoded, so it can't go stale when the underlying files are updated
    # (bit us once already: a hardcoded "Feb-Oct 2025" survived a Jan'25
    # data refresh and the model repeated the stale range as fact).
    return SYSTEM_PROMPT_TEMPLATE.format(
        loss_date_range=_date_range_str(losses),
        theft_date_range=_date_range_str(theft),
        divisions=", ".join(sorted(losses["Division"].dropna().unique())),
    )


def stream_ask(
    question: str,
    losses,
    theft,
    chat_history: list[dict] | None = None,
    uploaded_context: str | None = None,
) -> Iterator[dict]:
    """chat_history: list of {"role": "user"|"assistant", "content": str} from prior turns.
    uploaded_context: concatenated extracted text of files attached to this session, if any.
    """
    client = _get_client()
    messages = [{"role": "system", "content": _build_system_prompt(losses, theft)}]
    if uploaded_context:
        messages.append({"role": "system", "content": UPLOADED_DOCS_SYSTEM_TEMPLATE.format(context=uploaded_context)})
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    charts: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            stream=True,
        )

        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict] = {}

        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta

            if delta and delta.content:
                content_parts.append(delta.content)
                yield {"type": "token", "text": delta.content}

            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    acc = tool_calls_acc.setdefault(tc_delta.index, {"id": None, "name": None, "arguments": ""})
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        acc["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        acc["arguments"] += tc_delta.function.arguments

        full_content = "".join(content_parts) or None

        if tool_calls_acc:
            tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
            messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls_list
                ],
            })

            for tc in tool_calls_list:
                try:
                    kwargs = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    kwargs = {}
                content, chart = dispatch(tc["name"], kwargs, losses, theft)
                if chart is not None:
                    charts.append(chart)
                yield {"type": "tool_result", "tool": tc["name"], "chart": chart}
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": content})
            continue

        yield {"type": "done", "answer": full_content or "", "charts": charts}
        return

    yield {
        "type": "done",
        "answer": "I gathered the data but couldn't finish reasoning about it in time. Try narrowing your question.",
        "charts": charts,
    }
