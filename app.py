import requests
import re
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

import streamlit as st

URL = "https://dpboss.tax/"
HISTORY_FILE = Path("history.jsonl")

MIRROR_MAP = {
    0: 5, 1: 6, 2: 7, 3: 8, 4: 9,
    5: 0, 6: 1, 7: 2, 8: 3, 9: 4
}

st.set_page_config(
    page_title="Smart Kalyan Analyzer",
    page_icon="📊",
    layout="centered"
)


def fetch_results():
    """Extract possible two-digit numbers from the webpage."""
    response = requests.get(
        URL,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()

    # Remove script and style contents before extracting text.
    page = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        response.text,
        flags=re.I | re.S
    )
    page = re.sub(r"<[^>]+>", " ", page)
    page = re.sub(r"&nbsp;|&#160;", " ", page, flags=re.I)

    # Keep standalone two-digit numbers.
    numbers = re.findall(r"(?<!\d)\d{2}(?!\d)", page)

    if not numbers:
        raise ValueError(
            "No two-digit numbers found. The website may have changed."
        )

    return [int(x) for x in numbers[-100:]]


def analyze(data):
    if not data:
        return [], [], [], Counter()

    open_freq = Counter()
    close_freq = Counter()
    pair_freq = Counter()

    total = len(data)

    for i, number in enumerate(data):
        digits = f"{number:02d}"
        weight = 1 + i / max(1, total - 1)

        open_freq[int(digits[0])] += weight
        close_freq[int(digits[1])] += weight
        pair_freq[number] += 1

    top_open = [d for d, _ in open_freq.most_common(3)]
    top_close = [d for d, _ in close_freq.most_common(3)]

    candidates = {}

    for o in range(10):
        for c in range(10):
            pair = o * 10 + c

            score = (
                open_freq[o]
                + close_freq[c]
                + pair_freq[pair] * 1.5
            )
            candidates[pair] = score

            mirror = MIRROR_MAP[o] * 10 + MIRROR_MAP[c]
            mirror_score = score * 0.85

            candidates[mirror] = max(
                candidates.get(mirror, 0),
                mirror_score
            )

    ranked = sorted(
        candidates.items(),
        key=lambda item: item[1],
        reverse=True
    )

    max_score = ranked[0][1] if ranked else 1

    top_pairs = [
        {
            "Jodi": f"{pair:02d}",
            "Relative score": round(score / max_score * 100),
            "Historical occurrences": pair_freq[pair]
        }
        for pair, score in ranked[:10]
    ]

    return top_pairs, top_open, top_close, pair_freq


def save_history(record):
    """Save history when the hosting filesystem permits it."""
    with HISTORY_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


st.title("📊 Smart Kalyan Analyzer")
st.caption("Historical digit-frequency analysis")

st.info(
    "Scores are relative rankings, not winning probabilities. "
    "Historical patterns cannot reliably predict future results."
)

with st.expander("Data source and limitations"):
    st.write("Source:", URL)
    st.write(
        "This basic parser extracts two-digit numbers from webpage text. "
        "It does not confirm that every extracted number is an actual "
        "result. Dates and unrelated numbers may be included."
    )

if st.button("🔄 Fetch Data & Analyze", type="primary",
             use_container_width=True):
    try:
        with st.spinner("Fetching website data..."):
            data = fetch_results()

        pairs, open_digits, close_digits, pair_freq = analyze(data)

        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        st.session_state["analysis"] = {
            "data": data,
            "pairs": pairs,
            "open": open_digits,
            "close": close_digits,
            "time": timestamp
        }

        try:
            save_history({
                "timestamp": timestamp,
                "source": URL,
                "data": data,
                "rankings": pairs,
                "open_digits": open_digits,
                "close_digits": close_digits
            })
        except OSError:
            pass

    except requests.RequestException as error:
        st.error(f"Website request failed: {error}")
    except Exception as error:
        st.error(f"Analysis failed: {error}")

result = st.session_state.get("analysis")

if result:
    st.success("Analysis completed")
    st.caption(f"Last analyzed: {result['time']}")

    st.metric("Numbers extracted", len(result["data"]))

    st.subheader("🔥 Top 10 Jodi Rankings")
    st.dataframe(
        result["pairs"],
        use_container_width=True,
        hide_index=True
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Open digits")
        st.write(", ".join(map(str, result["open"])))

    with col2:
        st.subheader("📊 Close digits")
        st.write(", ".join(map(str, result["close"])))

    with st.expander("View extracted data"):
        st.write(result["data"])

    download_text = "\n".join(
        f"{item['Jodi']},{item['Relative score']},"
        f"{item['Historical occurrences']}"
        for item in result["pairs"]
    )

    st.download_button(
        "⬇️ Download rankings CSV",
        data="Jodi,Relative score,Historical occurrences\n"
             + download_text,
        file_name="jodi_rankings.csv",
        mime="text/csv",
        use_container_width=True
    )
else:
    st.write("Click the button above to start your analysis.")
