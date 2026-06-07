import streamlit as st
from google import genai
from google.genai import types
import json
import re
import time
from PIL import Image
import io

st.set_page_config(
    page_title="recAIcle — AI Waste Sorting",
    page_icon="♻️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash-lite"

COMPOSITE_INSTRUCTION = """
COMPOSITE MATERIALS: If the item has multiple components made of different materials
(e.g. a pudding cup with a film lid, a bottle with a paper label, a Tetra Pak carton,
a pizza box with a plastic window), list EACH component separately in the instructions field.
Format each component as: "[Part name]: [preparation] → [bin name]"
For the main 'bin' field, use the bin for the largest/primary component.
"""

REGULATIONS = {
    "🇹🇼 Taiwan": {
        "bins": {
            "recyclable": {"label": "資源回收 Recyclable",   "color": "#4dff91", "emoji": "♻️"},
            "food_waste": {"label": "廚餘 Food Waste",        "color": "#a8d060", "emoji": "🌱"},
            "general":    {"label": "一般垃圾 General Waste", "color": "#aaaaaa", "emoji": "🗑️"},
            "hazardous":  {"label": "有害廢棄物 Hazardous",   "color": "#ff6060", "emoji": "☠️"},
            "bulky":      {"label": "大型廢棄物 Bulky Waste", "color": "#60a0ff", "emoji": "🪑"},
        },
        "prompt": """You are a waste sorting expert for Taiwan.

RECYCLABLE (資源回收):
- Paper: newspapers, cardboard, books, paper bags, envelopes, receipts
- Plastics: PET, HDPE, PP bottles and containers (clean)
- Glass: bottles and jars (clean)
- Metals: aluminum and steel cans (rinsed)
- Cartons/Tetra Pak: milk cartons, juice boxes (rinsed)
- Clean styrofoam, clean plastic bags and films
- Clothing, shoes, bags (clean)
- Used cooking oil (sealed in bottle)
- Small electronics, batteries, fluorescent tubes

FOOD WASTE (廚餘):
- Raw scraps (生廚餘): vegetable peels, fruit cores, eggshells, tea leaves, coffee grounds
- Cooked food (熟廚餘): leftover cooked food, bones, rice, noodles

GENERAL WASTE (一般垃圾):
- Soiled or greasy packaging, tissues, diapers, sanitary products
- Ceramics, dishes, mirrors, non-bottle glassware
- Rubber, leather, plastic toys, wax-coated paper, photographs

HAZARDOUS (有害廢棄物):
- All batteries, fluorescent bulbs, medicines, paint, pesticides

BULKY (大型廢棄物):
- Furniture, large appliances (requires prior booking)

""" + COMPOSITE_INSTRUCTION + """
Reply ONLY with valid JSON:
{"item":"[English name]","bin":"[recyclable/food_waste/general/hazardous/bulky]","binLabel":"[label]","emoji":"[emoji]","instructions":["step or [Part]: [prep] → [bin]"],"note":"[one key Taiwan tip if needed]","confidence":"[high/medium/low]"}"""
    },

    "🇯🇵 Japan": {
        "bins": {
            "moeru":   {"label": "燃えるゴミ Burnable",       "color": "#ff8c42", "emoji": "🔥"},
            "moenai":  {"label": "燃えないゴミ Non-burnable", "color": "#6090ff", "emoji": "🪨"},
            "shigen":  {"label": "資源ゴミ Recyclable",       "color": "#4dff91", "emoji": "♻️"},
            "pet":     {"label": "ペットボトル PET Bottles",  "color": "#40c0ff", "emoji": "🧴"},
            "sodai":   {"label": "粗大ゴミ Oversized",        "color": "#c060ff", "emoji": "🪑"},
            "kikenna": {"label": "危険ゴミ Hazardous",        "color": "#ff4040", "emoji": "⚠️"},
        },
        "prompt": """You are a waste sorting expert for Japan. Use Tokyo 23-ward rules as default.

BURNABLE (燃えるゴミ):
- Food scraps, fruit peels, tea leaves, coffee grounds, bones
- Tissues, paper towels, soiled paper, wax-coated paper, shredded paper
- Clothing and shoes (soiled/worn), rubber, leather, wood scraps
- Small soft plastics with food residue, diapers, sanitary products

NON-BURNABLE (燃えないゴミ):
- Metal items under 30cm: pots, pans, cutlery, tools
- Ceramics, pottery, drinking glasses, mirrors, window glass
- Small appliances: hair dryers, irons, clocks, electric razors
- Umbrellas (under 30cm folded)

RECYCLABLE (資源ゴミ):
- Paper: newspapers, cardboard (flattened), magazines
- Glass bottles: clear, brown, other colors (rinsed, caps removed)
- Aluminum cans and steel cans (rinsed)
- Clean clothing and textiles (古着)

PET BOTTLES (ペットボトル):
- Only bottles with the ペットボトル mark
- Remove cap, remove label, rinse, crush flat

OVERSIZED (粗大ゴミ):
- Any item over 30cm: furniture, bicycles, large appliances
- Air conditioners, TVs, fridges, washing machines → Home Appliance Recycling Law

HAZARDOUS (危険ゴミ):
- Spray cans (completely empty, punctured), cassette gas cartridges
- Batteries → collection boxes at convenience stores

""" + COMPOSITE_INSTRUCTION + """
Reply ONLY with valid JSON:
{"item":"[English name]","bin":"[moeru/moenai/shigen/pet/sodai/kikenna]","binLabel":"[label]","emoji":"[emoji]","instructions":["step or [Part]: [prep] → [bin]"],"note":"[one key Japan tip, mention rules vary by ward]","confidence":"[high/medium/low]"}"""
    },

    "🇫🇷 France": {
        "bins": {
            "jaune":       {"label": "Bac Jaune Yellow Bin",        "color": "#ffe040", "emoji": "🟡"},
            "vert":        {"label": "Conteneur Verre Glass",       "color": "#40c060", "emoji": "🟢"},
            "gris":        {"label": "Bac Gris General Waste",      "color": "#aaaaaa", "emoji": "🗑️"},
            "brun":        {"label": "Bac Brun Organic",            "color": "#a05030", "emoji": "🟤"},
            "dechetterie": {"label": "Déchèterie Special Drop-off", "color": "#ff8040", "emoji": "🏭"},
        },
        "prompt": """You are a waste sorting expert for France. Apply national rules (2023 extension + 2024 biodéchets law).

BAC JAUNE (Yellow bin — ALL packaging):
- All plastics: bottles, yogurt pots, trays, bags, films (since 2023 — ALL plastics)
- All cardboard and paper: boxes, newspapers, magazines, paper bags (flattened)
- All metals: cans, tins, aluminum foil, empty aerosol cans, bottle caps
- Cartons/Tetra Pak: milk, juice, soup (rinsed and flattened)
- Pizza boxes: yellow bin even if slightly greasy (remove food scraps first)

CONTENEUR VERRE (Glass container — glass only):
- Glass bottles, jars, preserve pots
- NOT: drinking glasses, pyrex, mirrors, ceramics, light bulbs → gray bin
- Glass goes in street-side containers, not household bins
- Paris exception: green bin = general waste; glass goes in white street containers

BAC GRIS (Gray bin — non-recyclable):
- Tissues, paper towels, diapers, sanitary products, cat litter
- Ceramics, dishes, mirrors, drinking glasses, pyrex
- Extremely soiled packaging

BAC BRUN (Brown bin — organic, mandatory since Jan 2024):
- Vegetable and fruit peels, eggshells, coffee grounds, tea bags
- Cooked food leftovers, bread, meat, fish scraps

DECHETTERIE (Special drop-off):
- Large furniture and appliances
- Electronics (also at retailers), batteries (at stores), paint, chemicals
- Textiles → street collection bins (Le Relais, Emmaüs)
- Medicines → pharmacy

""" + COMPOSITE_INSTRUCTION + """
Reply ONLY with valid JSON:
{"item":"[English name]","bin":"[jaune/vert/gris/brun/dechetterie]","binLabel":"[label]","emoji":"[emoji]","instructions":["step or [Part]: [prep] → [bin]"],"note":"[one key France tip if needed]","confidence":"[high/medium/low]"}"""
    },
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #0d1f0f; color: #e8f5eb; }
.block-container { max-width: 560px !important; padding: 2rem 1.5rem !important; }
#MainMenu, footer, header { visibility: hidden; }
h1 {
    font-family: 'Syne', sans-serif !important;
    font-size: 2.2rem !important; font-weight: 800 !important;
    color: #4dff91 !important; letter-spacing: -1px !important; margin-bottom: 0 !important;
}
.subtitle { color: #4a6650; font-size: 14px; margin-bottom: 1.5rem; margin-top: 2px; }
[data-testid="stFileUploader"] {
    background: #071209 !important;
    border: 1px dashed rgba(77,255,145,0.25) !important;
    border-radius: 16px !important; padding: 8px !important;
}
[data-testid="stTextInput"] input {
    background: #071209 !important; border: 1px solid #1e3622 !important;
    border-radius: 12px !important; color: #e8f5eb !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: rgba(77,255,145,0.4) !important; box-shadow: none !important;
}
.stButton > button[kind="primary"] {
    background: #4dff91 !important; color: #071209 !important;
    border: none !important; border-radius: 12px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
    width: 100% !important; padding: 0.6rem !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: #071209 !important; border-radius: 12px !important; gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; border-radius: 10px !important;
    color: #4a6650 !important; font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(77,255,145,0.12) !important;
    color: #4dff91 !important; border-bottom: none !important;
}
.result-card {
    background: #111f13; border: 1px solid #1e3622;
    border-radius: 20px; padding: 20px; margin-top: 16px;
    animation: slideUp 0.4s ease;
}
@keyframes slideUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:none} }
.result-item { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#e8f5eb; letter-spacing:-0.5px; }
.country-tag {
    display:inline-block; background:rgba(77,255,145,0.08);
    border:1px solid rgba(77,255,145,0.18); color:#4dff91; font-size:11px; font-weight:600;
    padding:3px 10px; border-radius:100px; margin-top:6px; margin-bottom:14px; letter-spacing:0.5px;
}
.bin-box { border-radius:14px; padding:14px 16px; margin-bottom:14px; }
.bin-label { font-size:10px; font-weight:600; letter-spacing:0.5px; opacity:0.6; margin-bottom:4px; }
.bin-name  { font-family:'Syne',sans-serif; font-size:19px; font-weight:700; }
.steps-title { font-size:10px; font-weight:600; letter-spacing:0.5px; color:#4a6650; margin-bottom:8px; }
.step-item {
    background:#0d1f0f; border-radius:10px; padding:9px 12px; margin-bottom:6px;
    display:flex; gap:10px; align-items:flex-start; font-size:13px; color:#a8c0ac; line-height:1.5;
}
.step-item.composite { background:#0a1e12; border-left: 2px solid rgba(77,255,145,0.3); }
.step-arrow { color:#4dff91; font-weight:700; }
.note-box {
    background:rgba(255,200,0,0.04); border:1px solid rgba(255,200,0,0.12);
    border-radius:10px; padding:10px 14px; font-size:12px; color:#7a8060; line-height:1.6; margin-top:6px;
}
.note-label { color:#c6a020; font-weight:600; }
.conf-badge { font-size:10px; font-weight:600; letter-spacing:0.5px; margin-left:8px; }
[data-testid="stSelectbox"] > div {
    background:#071209 !important; border:1px solid #1e3622 !important;
    border-radius:12px !important; color:#e8f5eb !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────
for key, default in {
    "photo_bytes": None,
    "photo_result": None,
    "photo_country": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def parse_json(text: str) -> dict:
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    text = re.sub(r"```json|```", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found")
    return json.loads(text[start:end+1])


def call_gemini(prompt: str, image: Image.Image = None) -> dict:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    for attempt in range(3):
        try:
            if image:
                buf = io.BytesIO()
                image.save(buf, format="JPEG")
                img_part = types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
                response = client.models.generate_content(
                    model=MODEL, contents=[img_part, prompt], config=config
                )
            else:
                response = client.models.generate_content(
                    model=MODEL, contents=prompt, config=config
                )
            return parse_json(response.text)
        except Exception as e:
            err = str(e)
            if "503" in err or "UNAVAILABLE" in err or "429" in err or "RESOURCE_EXHAUSTED" in err:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    st.toast(f"⏳ Server busy, retrying in {wait}s... ({attempt + 1}/3)")
                    time.sleep(wait)
                else:
                    st.error("⚠️ Server is currently overloaded. Please try again in a moment.")
            else:
                st.error(f"AI error: {e}")
                return None
    return None


def render_result(data: dict, country: str):
    reg      = REGULATIONS[country]
    bin_key  = data.get("bin", "general")
    bin_info = reg["bins"].get(bin_key, {"label": data.get("binLabel", "?"), "color": "#4dff91", "emoji": "♻️"})
    conf_colors = {"high": "#4dff91", "medium": "#ffe040", "low": "#ff9090"}
    conf_color  = conf_colors.get(data.get("confidence", "high"), "#4dff91")
    flag = country.split()[0]

    steps_html = ""
    for step in data.get("instructions", []):
        if "→" in step:
            parts = step.split("→", 1)
            steps_html += f"""
            <div class="step-item composite">
              <span style="font-size:15px;flex-shrink:0">🔧</span>
              <span>{parts[0].strip()} <span class="step-arrow">→</span> {parts[1].strip()}</span>
            </div>"""
        else:
            steps_html += f"""
            <div class="step-item">
              <span style="font-size:15px;flex-shrink:0">✅</span>
              <span>{step}</span>
            </div>"""

    note_html = (
        f'<div class="note-box"><span class="note-label">📌 </span>{data["note"]}</div>'
        if data.get("note") else ""
    )

    st.markdown(f"""
    <div class="result-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div class="result-item">{data.get("item", "Item")}</div>
          <div class="country-tag">{flag} {country.split(" ", 1)[1]}
            <span class="conf-badge" style="color:{conf_color}">● {data.get("confidence", "").upper()}</span>
          </div>
        </div>
        <div style="font-size:36px;margin-top:4px">{data.get("emoji", bin_info["emoji"])}</div>
      </div>
      <div class="bin-box" style="background:{bin_info['color']}18;border:1px solid {bin_info['color']}33">
        <div class="bin-label" style="color:{bin_info['color']}">PRIMARY BIN</div>
        <div class="bin-name" style="color:{bin_info['color']}">{bin_info['emoji']} {bin_info['label']}</div>
      </div>
      <div class="steps-title">HOW TO SORT</div>
      {steps_html}
      {note_html}
    </div>
    """, unsafe_allow_html=True)


# ── UI ────────────────────────────────────────────────────────
st.markdown('<h1>recAIcle</h1>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">AI-powered waste sorting · Point, snap, toss right.</div>', unsafe_allow_html=True)

country = st.selectbox("", list(REGULATIONS.keys()), label_visibility="collapsed")
st.markdown("---")

tab_photo, tab_text = st.tabs(["📷 Photo", "⌨️ Type Item"])

# ── Photo tab ─────────────────────────────────────────────────
with tab_photo:
    st.markdown(
        "<div style='color:#4a6650;font-size:13px;margin-bottom:10px'>"
        "Upload a photo or tap to take one with your camera.</div>",
        unsafe_allow_html=True
    )
    uploaded = st.file_uploader(
        "", type=["jpg", "jpeg", "png", "webp", "heic"],
        label_visibility="collapsed"
    )

    # New photo uploaded → store bytes and reset result
    if uploaded is not None:
        new_bytes = uploaded.read()
        if new_bytes != st.session_state.photo_bytes:
            st.session_state.photo_bytes   = new_bytes
            st.session_state.photo_result  = None
            st.session_state.photo_country = country

    # Country changed → re-analyze same photo
    if (st.session_state.photo_bytes is not None and
            st.session_state.photo_country != country):
        st.session_state.photo_result  = None
        st.session_state.photo_country = country

    # Display stored photo
    if st.session_state.photo_bytes:
        image = Image.open(io.BytesIO(st.session_state.photo_bytes))
        st.image(image, use_column_width=True)

        # Analyze if no result yet
        if st.session_state.photo_result is None:
            with st.spinner("🔍 Analyzing..."):
                prompt = (
                    f"{REGULATIONS[country]['prompt']}\n\n"
                    f"Identify the waste item(s) in this image and tell me which bin each "
                    f"component goes in for {country.split(' ', 1)[1]}. Return only the JSON."
                )
                result = call_gemini(prompt, image)
            if result:
                st.session_state.photo_result = result

        if st.session_state.photo_result:
            render_result(st.session_state.photo_result, country)

# ── Text tab ──────────────────────────────────────────────────
with tab_text:
    st.markdown("Describe the item you want to sort.")
    col1, col2 = st.columns([4, 1])
    with col1:
        text_query = st.text_input(
            "", placeholder="e.g. pudding cup with film lid, pizza box...",
            label_visibility="collapsed"
        )
    with col2:
        ask_btn = st.button("Ask AI", type="primary", use_container_width=True)

    if ask_btn and text_query.strip():
        with st.spinner("🔍 Checking regulations..."):
            prompt = (
                f"{REGULATIONS[country]['prompt']}\n\n"
                f"How do I sort this item in {country.split(' ', 1)[1]}: "
                f'"{text_query.strip()}"? '
                f"If it has multiple components, break down each part separately. "
                f"Return only the JSON."
            )
            result = call_gemini(prompt)
        if result:
            render_result(result, country)
