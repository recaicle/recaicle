import streamlit as st
import google.generativeai as genai
import json
import re
from PIL import Image
import io

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="recAIcle — AI Waste Sorting",
    page_icon="♻️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── Gemini setup ─────────────────────────────────────────────
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# ── Regulation database ───────────────────────────────────────
REGULATIONS = {
    "🇹🇼 Taiwan": {
        "bins": {
            "recyclable":  {"label": "資源回收 Recyclable",        "color": "#4dff91", "emoji": "♻️"},
            "food_waste":  {"label": "廚餘 Food Waste",             "color": "#a8d060", "emoji": "🌱"},
            "general":     {"label": "一般垃圾 General Waste",      "color": "#aaaaaa", "emoji": "🗑️"},
            "hazardous":   {"label": "有害廢棄物 Hazardous",        "color": "#ff6060", "emoji": "☠️"},
            "bulky":       {"label": "大型廢棄物 Bulky Waste",      "color": "#60a0ff", "emoji": "🪑"},
        },
        "prompt": """You are a waste sorting expert for Taiwan. Taiwan has strict government-enforced waste sorting.

Categories:
- recyclable: Clean plastics (PET/HDPE/PP), paper, glass bottles, metals, cartons, e-waste, clean styrofoam, clean plastic bags
- food_waste: Raw food scraps (生廚餘) for composting, cooked food (熟廚餘) for pig feed
- general: Soiled items, tissues, dirty packaging, rubber, leather, non-recyclable plastics
- hazardous: Batteries, fluorescent bulbs, pharmaceuticals, paint
- bulky: Furniture, large appliances (need prior appointment with district office)

Key rules: Garbage trucks come at specific times; residents bring trash directly to truck. Recyclables must be clean and dry. Pizza boxes with grease → general. Receipts (統一發票) → recyclable paper.

Reply ONLY with valid JSON, no markdown fences:
{"item":"[English name]","bin":"[recyclable/food_waste/general/hazardous/bulky]","binLabel":"[label]","emoji":"[emoji]","instructions":["step1","step2","step3"],"note":"[Taiwan-specific tip]","confidence":"[high/medium/low]"}"""
    },

    "🇯🇵 Japan": {
        "bins": {
            "moeru":   {"label": "燃えるゴミ Burnable",        "color": "#ff8c42", "emoji": "🔥"},
            "moenai":  {"label": "燃えないゴミ Non-burnable",  "color": "#6090ff", "emoji": "🪨"},
            "shigen":  {"label": "資源ゴミ Recyclable",        "color": "#4dff91", "emoji": "♻️"},
            "pet":     {"label": "ペットボトル PET Bottles",   "color": "#40c0ff", "emoji": "🧴"},
            "sodai":   {"label": "粗大ゴミ Oversized",         "color": "#c060ff", "emoji": "🪑"},
            "kikenna": {"label": "危険ゴミ Hazardous",         "color": "#ff4040", "emoji": "⚠️"},
        },
        "prompt": """You are a waste sorting expert for Japan (Tokyo standard rules).

Categories:
- moeru: Food waste, soiled paper, wood, rubber, leather, sanitary items, small plastics with residue, dirty clothing
- moenai: Metal items under 30cm, ceramics, glass (non-bottle), small appliances, umbrellas
- shigen: Newspapers (tied), cardboard (flattened), magazines, glass bottles, aluminum/steel cans, clean textiles
- pet: PET bottles ONLY — remove cap, remove label, rinse, crush flat
- sodai: Items over 30cm — requires advance booking and fee sticker
- kikenna: Empty spray cans (punctured), lighters

Key rules: Plastic packaging with プラ mark → moeru if dirty. PET caps → moeru or charity. Batteries → convenience store collection points. Never mix categories.

Reply ONLY with valid JSON, no markdown fences:
{"item":"[English name]","bin":"[moeru/moenai/shigen/pet/sodai/kikenna]","binLabel":"[label]","emoji":"[emoji]","instructions":["step1","step2","step3"],"note":"[Japan-specific tip]","confidence":"[high/medium/low]"}"""
    },

    "🇫🇷 France": {
        "bins": {
            "jaune":       {"label": "Bac Jaune Yellow Bin",        "color": "#ffe040", "emoji": "🟡"},
            "vert":        {"label": "Conteneur Verre Glass",       "color": "#40c060", "emoji": "🟢"},
            "gris":        {"label": "Bac Gris General Waste",      "color": "#aaaaaa", "emoji": "🗑️"},
            "brun":        {"label": "Bac Brun Organic",            "color": "#a05030", "emoji": "🟤"},
            "dechetterie": {"label": "Déchèterie Special Drop-off", "color": "#ff8040", "emoji": "🏭"},
        },
        "prompt": """You are a waste sorting expert for France (post-2023/2024 updated rules).

Categories:
- jaune: ALL packaging — plastic bottles, ALL plastics since 2023 extension (yogurt pots, trays, bags), cardboard (flattened), metal cans, Tetra Pak, paper, newspapers
- vert: Glass bottles and jars ONLY. Not ceramics, pyrex, mirrors, or bulbs. Goes in street glass containers.
- gris: Non-recyclable waste — soiled packaging, diapers, cat litter, ceramics, tissues
- brun: Food scraps, vegetable peelings, coffee grounds, eggshells, small soiled cardboard. Mandatory since Jan 2024.
- dechetterie: Large items, electronics (DEEE), batteries, paint, chemicals. Textiles → street bins. Medications → pharmacy.

Key rules: Since 2023 ALL plastics go in yellow bin. Pizza boxes → jaune if lightly soiled, gris if very greasy. Glass NEVER goes in yellow bin.

Reply ONLY with valid JSON, no markdown fences:
{"item":"[English name]","bin":"[jaune/vert/gris/brun/dechetterie]","binLabel":"[label]","emoji":"[emoji]","instructions":["step1","step2","step3"],"note":"[France-specific tip, mention 2023/2024 changes if relevant]","confidence":"[high/medium/low]"}"""
    },
}

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
.stApp {
    background: #0d1f0f;
    color: #e8f5eb;
}
.block-container { max-width: 560px !important; padding: 2rem 1.5rem !important; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

h1 {
    font-family: 'Syne', sans-serif !important;
    font-size: 2.2rem !important;
    font-weight: 800 !important;
    color: #4dff91 !important;
    letter-spacing: -1px !important;
    margin-bottom: 0 !important;
}
.subtitle {
    color: #4a6650; font-size: 14px; margin-bottom: 1.5rem; margin-top: 2px;
}

/* Country selector */
div[data-testid="stHorizontalBlock"] button {
    border-radius: 100px !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #071209 !important;
    border: 1px dashed rgba(77,255,145,0.25) !important;
    border-radius: 16px !important;
    padding: 8px !important;
}
[data-testid="stFileUploader"] label {
    color: #4dff91 !important;
}

/* Text input */
[data-testid="stTextInput"] input {
    background: #071209 !important;
    border: 1px solid #1e3622 !important;
    border-radius: 12px !important;
    color: #e8f5eb !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: rgba(77,255,145,0.4) !important;
    box-shadow: none !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
    background: #4dff91 !important;
    color: #071209 !important;
    border: none !important;
    border-radius: 12px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    width: 100% !important;
    padding: 0.6rem !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 0 20px rgba(77,255,145,0.4) !important;
    transform: translateY(-1px) !important;
}

/* Result card */
.result-card {
    background: #111f13;
    border: 1px solid #1e3622;
    border-radius: 20px;
    padding: 20px;
    margin-top: 16px;
    animation: slideUp 0.4s ease;
}
@keyframes slideUp {
    from { opacity:0; transform: translateY(12px); }
    to   { opacity:1; transform: none; }
}
.result-item { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#e8f5eb; letter-spacing:-0.5px; }
.country-tag {
    display:inline-block;
    background: rgba(77,255,145,0.08);
    border: 1px solid rgba(77,255,145,0.18);
    color: #4dff91; font-size:11px; font-weight:600;
    padding: 3px 10px; border-radius:100px; margin-top:6px; margin-bottom:14px;
    letter-spacing:0.5px;
}
.bin-box {
    border-radius: 14px; padding: 14px 16px; margin-bottom: 14px;
}
.bin-label { font-size:10px; font-weight:600; letter-spacing:0.5px; opacity:0.6; margin-bottom:4px; }
.bin-name  { font-family:'Syne',sans-serif; font-size:19px; font-weight:700; }
.steps-title { font-size:10px; font-weight:600; letter-spacing:0.5px; color:#4a6650; margin-bottom:8px; }
.step-item {
    background: #0d1f0f; border-radius: 10px;
    padding: 9px 12px; margin-bottom:6px;
    display:flex; gap:10px; align-items:flex-start;
    font-size:13px; color:#a8c0ac; line-height:1.5;
}
.note-box {
    background: rgba(255,200,0,0.04);
    border: 1px solid rgba(255,200,0,0.12);
    border-radius: 10px; padding: 10px 14px;
    font-size:12px; color:#7a8060; line-height:1.6; margin-top:6px;
}
.note-label { color:#c6a020; font-weight:600; }
.conf-badge { font-size:10px; font-weight:600; letter-spacing:0.5px; margin-left:8px; }

/* Divider */
.divider { display:flex; align-items:center; gap:10px; color:#2e4832; font-size:12px; margin:8px 0; }
.divider::before,.divider::after { content:''; flex:1; height:1px; background:#1e3622; }

/* Selectbox */
[data-testid="stSelectbox"] > div {
    background: #071209 !important;
    border: 1px solid #1e3622 !important;
    border-radius: 12px !important;
    color: #e8f5eb !important;
}
</style>
""", unsafe_allow_html=True)

# ── Helper ────────────────────────────────────────────────────
def parse_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end+1])

def call_gemini(prompt: str, image: Image.Image = None) -> dict:
    try:
        if image:
            response = model.generate_content([prompt, image])
        else:
            response = model.generate_content(prompt)
        return parse_json(response.text)
    except Exception as e:
        st.error(f"AI error: {e}")
        return None

def render_result(data: dict, country: str):
    reg = REGULATIONS[country]
    bin_key = data.get("bin", "general")
    bin_info = reg["bins"].get(bin_key, {"label": data.get("binLabel","?"), "color":"#4dff91", "emoji":"♻️"})
    conf_colors = {"high":"#4dff91","medium":"#ffe040","low":"#ff9090"}
    conf_color = conf_colors.get(data.get("confidence","high"), "#4dff91")
    flag = country.split()[0]

    steps_html = "".join(
        f'<div class="step-item"><span>✅</span><span>{s}</span></div>'
        for s in data.get("instructions", [])
    )
    note_html = f'<div class="note-box"><span class="note-label">📌 Note: </span>{data["note"]}</div>' if data.get("note") else ""

    st.markdown(f"""
    <div class="result-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div class="result-item">{data.get("item","Item")}</div>
          <div class="country-tag">{flag} {country.split(" ",1)[1]}
            <span class="conf-badge" style="color:{conf_color}">● {data.get("confidence","").upper()}</span>
          </div>
        </div>
        <div style="font-size:36px;margin-top:4px">{data.get("emoji", bin_info["emoji"])}</div>
      </div>
      <div class="bin-box" style="background:{bin_info['color']}18;border:1px solid {bin_info['color']}33">
        <div class="bin-label" style="color:{bin_info['color']}">THROW INTO</div>
        <div class="bin-name" style="color:{bin_info['color']}">{bin_info['emoji']} {bin_info['label']}</div>
      </div>
      <div class="steps-title">HOW TO PREPARE</div>
      {steps_html}
      {note_html}
    </div>
    """, unsafe_allow_html=True)

# ── UI ────────────────────────────────────────────────────────
st.markdown('<h1>recAIcle</h1>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">AI-powered waste sorting · Point, snap, toss right.</div>', unsafe_allow_html=True)

# Country selector
country = st.selectbox("", list(REGULATIONS.keys()), label_visibility="collapsed")

st.markdown("---")

# Photo upload
st.markdown("#### 📷 Upload a photo")
uploaded = st.file_uploader("", type=["jpg","jpeg","png","webp"], label_visibility="collapsed")

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_column_width=True)
    with st.spinner("🔍 Analyzing with AI..."):
        prompt = f"{REGULATIONS[country]['prompt']}\n\nIdentify the main waste item in this image and tell me how to sort it in {country.split(' ',1)[1]}. Return only the JSON."
        result = call_gemini(prompt, image)
    if result:
        render_result(result, country)

st.markdown('<div class="divider">or type the item name</div>', unsafe_allow_html=True)

# Text search
col1, col2 = st.columns([4, 1])
with col1:
    text_query = st.text_input("", placeholder="e.g. plastic bottle, pizza box, milk carton...", label_visibility="collapsed")
with col2:
    ask_btn = st.button("Ask AI", type="primary", use_container_width=True)

if ask_btn and text_query.strip():
    with st.spinner("🔍 Checking regulations..."):
        prompt = f"{REGULATIONS[country]['prompt']}\n\nHow do I sort this item in {country.split(' ',1)[1]}: \"{text_query.strip()}\"? Return only the JSON."
        result = call_gemini(prompt)
    if result:
        render_result(result, country)
