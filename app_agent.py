import streamlit as st
from google import genai
from google.genai import types
import json, re, time, html as html_lib
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

# ── Regulation database ───────────────────────────────────────
REGULATIONS = {
    "🇹🇼 Taiwan": {
        "bins": {
            "recyclable": {"label": "資源回收 Recyclable",   "color": "#4dff91", "emoji": "♻️"},
            "food_waste": {"label": "廚餘 Food Waste",        "color": "#a8d060", "emoji": "🌱"},
            "general":    {"label": "一般垃圾 General Waste", "color": "#aaaaaa", "emoji": "🗑️"},
            "hazardous":  {"label": "有害廢棄物 Hazardous",   "color": "#ff6060", "emoji": "☠️"},
            "bulky":      {"label": "大型廢棄物 Bulky Waste", "color": "#60a0ff", "emoji": "🪑"},
        },
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
    },
    "🇫🇷 France": {
        "bins": {
            "jaune":       {"label": "Bac Jaune Yellow Bin",        "color": "#ffe040", "emoji": "🟡"},
            "vert":        {"label": "Conteneur Verre Glass",       "color": "#40c060", "emoji": "🟢"},
            "gris":        {"label": "Bac Gris General Waste",      "color": "#aaaaaa", "emoji": "🗑️"},
            "brun":        {"label": "Bac Brun Organic",            "color": "#a05030", "emoji": "🟤"},
            "dechetterie": {"label": "Déchèterie Special Drop-off", "color": "#ff8040", "emoji": "🏭"},
        },
    },
}

COUNTRY_CODE_MAP = {"tw": "🇹🇼 Taiwan", "jp": "🇯🇵 Japan", "fr": "🇫🇷 France"}
COUNTRY_NAME_TO_CODE = {"🇹🇼 Taiwan": "tw", "🇯🇵 Japan": "jp", "🇫🇷 France": "fr"}

# Material → bin key mapping per country
MATERIAL_BIN_MAP = {
    "tw": {
        "plastic": "recyclable", "glass": "recyclable", "metal": "recyclable",
        "paper": "recyclable", "cardboard": "recyclable", "organic": "food_waste",
        "electronic": "hazardous", "textile": "recyclable", "hazardous": "hazardous",
        "mixed": "general",
    },
    "jp": {
        "plastic": "moeru", "glass": "moenai", "metal": "moenai",
        "paper": "shigen", "cardboard": "shigen", "organic": "moeru",
        "electronic": "sodai", "textile": "shigen", "hazardous": "kikenna",
        "mixed": "moeru",
    },
    "fr": {
        "plastic": "jaune", "glass": "vert", "metal": "jaune",
        "paper": "jaune", "cardboard": "jaune", "organic": "brun",
        "electronic": "dechetterie", "textile": "dechetterie",
        "hazardous": "dechetterie", "mixed": "gris",
    },
}

# Country-specific regulation texts per material
REGULATION_NOTES = {
    "tw": {
        "plastic":   "Rinse clean before recycling. Labels do NOT need to be removed in Taiwan.",
        "glass":     "Remove caps/lids. Rinse clean.",
        "metal":     "Rinse cans. Crush to save space.",
        "paper":     "Keep dry. Grease-soiled paper goes to general waste.",
        "cardboard": "Flatten before recycling.",
        "organic":   "Separate raw (生廚餘) for composting and cooked (熟廚餘) for pig feed.",
        "hazardous": "Return to designated collection at convenience stores or hand to recycling truck.",
        "electronic":"Hand to recycling truck or designated e-waste collection point.",
    },
    "jp": {
        "plastic":   "Plastic packaging with プラ mark → recyclable in many Tokyo wards. Otherwise → burnable. Rules vary by ward.",
        "glass":     "Glass bottles → resource garbage (shigen). Glassware/cups → non-burnable (moenai).",
        "metal":     "Items under 30cm → non-burnable. Cans → resource garbage (rinsed).",
        "paper":     "Bundle separately: newspapers / magazines / cardboard. Put out on resource garbage day.",
        "cardboard": "Flatten and tie with string. Put out on resource garbage day.",
        "organic":   "Drain excess liquid. Wrap in newspaper to reduce odour.",
        "hazardous": "Spray cans must be completely empty and punctured. Batteries → convenience store boxes.",
        "electronic":"Items over 30cm → oversized (粗大ゴミ). Book in advance.",
        "textile":   "Clean clothing → resource garbage. Soiled/torn → burnable.",
    },
    "fr": {
        "plastic":   "Since 2023: ALL plastics go in yellow bin (bac jaune) — including yogurt pots, trays and bags.",
        "glass":     "Glass ONLY in street-side glass containers (conteneur verre). NEVER in yellow bin. ⚠️ Paris: glass goes in white containers.",
        "metal":     "Rinse cans. Aerosol cans in yellow bin only if completely empty.",
        "paper":     "Yellow bin. Keep dry.",
        "cardboard": "Flatten before placing in yellow bin.",
        "organic":   "Mandatory since January 2024 (Loi AGEC). Use compostable bags or newspaper.",
        "hazardous": "Take to déchèterie. Batteries → collection boxes at supermarkets. Medicines → pharmacy.",
        "textile":   "Street collection bins (Le Relais, Emmaüs) or in-store collection.",
    },
}

# ── Agentic AI Tools ──────────────────────────────────────────
TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="identify_waste_item",
            description=(
                "Step 1 — Analyze the image or text description to identify the waste item. "
                "Determine its common name, primary material type, and whether it has multiple "
                "separable components that may belong to different waste bins."
            ),
            parameters={
                "type": "OBJECT",
                "properties": {
                    "item_name": {
                        "type": "STRING",
                        "description": "Common English name of the waste item (e.g. 'PET plastic bottle')"
                    },
                    "primary_material": {
                        "type": "STRING",
                        "enum": ["plastic","glass","metal","paper","cardboard",
                                 "organic","electronic","textile","hazardous","mixed"],
                        "description": "Primary material category"
                    },
                    "is_composite": {
                        "type": "BOOLEAN",
                        "description": "True if item has multiple separable components of different materials"
                    },
                    "components": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "part": {"type": "STRING"},
                                "material": {"type": "STRING"}
                            }
                        },
                        "description": "Separable components if composite (e.g. cap, label, body)"
                    },
                    "confidence": {
                        "type": "STRING",
                        "enum": ["high","medium","low"]
                    }
                },
                "required": ["item_name","primary_material","is_composite","confidence"]
            }
        ),
        types.FunctionDeclaration(
            name="query_regulation_database",
            description=(
                "Step 2 — Query the official waste regulation database to determine which bin "
                "a specific material belongs to in the given country. "
                "Call this for each component if the item is composite."
            ),
            parameters={
                "type": "OBJECT",
                "properties": {
                    "country_code": {
                        "type": "STRING",
                        "enum": ["tw","jp","fr"],
                        "description": "Country code: tw=Taiwan, jp=Japan, fr=France"
                    },
                    "material_type": {
                        "type": "STRING",
                        "description": "Material to look up"
                    },
                    "item_name": {
                        "type": "STRING",
                        "description": "Item or component name for context"
                    }
                },
                "required": ["country_code","material_type","item_name"]
            }
        ),
    ])
]


def execute_tool(name: str, args: dict, country_code: str) -> dict:
    """Execute a tool call against real regulation data."""
    if name == "identify_waste_item":
        return {
            "status": "identified",
            "item_name": args.get("item_name"),
            "primary_material": args.get("primary_material"),
            "is_composite": args.get("is_composite", False),
            "components": args.get("components", []),
            "confidence": args.get("confidence", "medium"),
        }

    elif name == "query_regulation_database":
        cc       = args.get("country_code", country_code)
        material = args.get("material_type", "mixed").lower()
        item     = args.get("item_name", "item")

        # Japan PET bottle special case
        if cc == "jp" and material == "plastic" and any(
            w in item.lower() for w in ["bottle","pet","ペット"]
        ):
            bin_key = "pet"
        else:
            bin_key = MATERIAL_BIN_MAP.get(cc, {}).get(material, "general")

        country_name = COUNTRY_CODE_MAP.get(cc, "🇹🇼 Taiwan")
        bins     = REGULATIONS.get(country_name, {}).get("bins", {})
        bin_info = bins.get(bin_key, {"label":"General Waste","color":"#aaa","emoji":"🗑️"})
        note     = REGULATION_NOTES.get(cc, {}).get(material, "")

        return {
            "status":    "success",
            "country":   country_name,
            "bin_key":   bin_key,
            "bin_label": bin_info["label"],
            "bin_color": bin_info["color"],
            "bin_emoji": bin_info["emoji"],
            "note":      note,
            "source":    f"Official {country_name.split()[1]} waste regulations",
        }

    return {"status": "error", "message": f"Unknown tool: {name}"}


def run_agent(prompt: str, country_code: str,
              image: Image.Image = None) -> tuple:
    """
    Agentic AI loop: AI decides which tools to call, calls them,
    reasons over results, and returns final sorting JSON.
    Returns (result_dict | None, agent_steps_list)
    """
    agent_steps = []

    # Build initial message
    initial_parts = []
    if image:
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        initial_parts.append(
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
        )
    initial_parts.append(types.Part(text=prompt))

    country_name = COUNTRY_CODE_MAP.get(country_code, "🇹🇼 Taiwan")
    system_text = f"""You are an expert waste sorting AI agent for {country_name}.

Workflow — follow in order:
1. Call identify_waste_item to analyze the item.
2. Call query_regulation_database (once per component if composite).
3. After all tool calls, respond with ONLY valid JSON (no markdown):

{{"item":"[name]","bin":"[bin_key from DB]","binLabel":"[label]","emoji":"[emoji]","instructions":["[Part/step]: [action] → [bin]"],"note":"[key tip]","confidence":"[high/medium/low]"}}

For composite items use "[Part]: [prep] → [bin]" format in instructions."""

    messages = [types.Content(role="user", parts=initial_parts)]

    config = types.GenerateContentConfig(
        system_instruction=system_text,
        tools=TOOLS,
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="auto")
        ),
    )

    for iteration in range(8):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=messages, config=config
            )
        except Exception as e:
            err = str(e)
            if "503" in err or "UNAVAILABLE" in err or "429" in err:
                if iteration < 3:
                    st.toast(f"⏳ Server busy, retrying… ({iteration+1})")
                    time.sleep(3)
                    continue
            return None, agent_steps

        content = response.candidates[0].content
        fn_calls = [p for p in content.parts
                    if hasattr(p, "function_call") and p.function_call
                    and p.function_call.name]

        if not fn_calls:
            # No more tool calls → extract JSON from final text
            text = "".join(
                p.text for p in content.parts
                if hasattr(p, "text") and p.text
            )
            text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
            text = re.sub(r"```json|```", "", text).strip()
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end == -1:
                return None, agent_steps
            try:
                return json.loads(text[start:end+1]), agent_steps
            except Exception:
                return None, agent_steps

        # ── Execute each function call ──
        messages.append(content)
        fn_response_parts = []

        for part in content.parts:
            if not (hasattr(part, "function_call") and part.function_call
                    and part.function_call.name):
                continue
            fc   = part.function_call
            args = dict(fc.args) if fc.args else {}
            result = execute_tool(fc.name, args, country_code)

            # Record for UI
            if fc.name == "identify_waste_item":
                detail = (
                    f"{args.get('item_name','?')} · "
                    f"{args.get('primary_material','?')} · "
                    f"{args.get('confidence','?').upper()} confidence"
                )
                if args.get("is_composite"):
                    comps = ", ".join(
                        c.get("part","?")
                        for c in args.get("components",[])[:4]
                    )
                    detail += f" · Parts: {comps}"
                label = "🔍 Identified item"
            elif fc.name == "query_regulation_database":
                detail = (
                    f"{args.get('item_name','?')} ({args.get('material_type','?')}) "
                    f"→ {result.get('bin_emoji','')} {result.get('bin_label','?')}"
                )
                label = "📋 Queried regulation database"
            else:
                detail = str(args)
                label = f"🔧 {fc.name}"

            agent_steps.append({"label": label, "detail": detail})

            fn_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response=result
                    )
                )
            )

        messages.append(types.Content(role="user", parts=fn_response_parts))

    return None, agent_steps


# ── CSS ───────────────────────────────────────────────────────
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
.stExpander { background: #071209 !important; border: 1px solid #1e3622 !important; border-radius: 12px !important; }
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
.step-item.composite { background:#0a1e12; border-left:2px solid rgba(77,255,145,0.3); }
.step-arrow { color:#4dff91; font-weight:700; }
.note-box {
    background:rgba(255,200,0,0.04); border:1px solid rgba(255,200,0,0.12);
    border-radius:10px; padding:10px 14px; font-size:12px; color:#7a8060; line-height:1.6; margin-top:6px;
}
.note-label { color:#c6a020; font-weight:600; }
.conf-badge { font-size:10px; font-weight:600; letter-spacing:0.5px; margin-left:8px; }
.agent-step {
    background:#071209; border:1px solid #1e3622; border-radius:10px;
    padding:10px 14px; margin-bottom:8px;
    font-size:13px; color:#7a9e82; line-height:1.6;
}
.agent-step-label { color:#4dff91; font-weight:600; margin-bottom:2px; font-size:12px; }
[data-testid="stSelectbox"] > div {
    background:#071209 !important; border:1px solid #1e3622 !important;
    border-radius:12px !important; color:#e8f5eb !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
for key, val in {"photo_bytes": None, "photo_result": None,
                 "photo_country": None, "photo_steps": []}.items():
    if key not in st.session_state:
        st.session_state[key] = val


def render_agent_steps(steps: list):
    if not steps:
        return
    with st.expander(f"🤖 Agent reasoning — {len(steps)} step(s)", expanded=False):
        for i, step in enumerate(steps, 1):
            st.markdown(
                f'<div class="agent-step">'
                f'<div class="agent-step-label">Step {i} · {step["label"]}</div>'
                f'{html_lib.escape(step["detail"])}'
                f'</div>',
                unsafe_allow_html=True
            )


def render_result(data: dict, country: str):
    reg      = REGULATIONS[country]
    bin_key  = data.get("bin", "general")
    bin_info = reg["bins"].get(bin_key, {"label": data.get("binLabel","?"), "color":"#4dff91","emoji":"♻️"})
    conf_colors = {"high":"#4dff91","medium":"#ffe040","low":"#ff9090"}
    conf_color  = conf_colors.get(data.get("confidence","high"), "#4dff91")
    flag = country.split()[0]

    steps_html = ""
    for step in data.get("instructions", []):
        if "→" in step:
            parts = step.split("→", 1)
            l, r = html_lib.escape(parts[0].strip()), html_lib.escape(parts[1].strip())
            steps_html += f'<div class="step-item composite"><span style="font-size:15px;flex-shrink:0">🔧</span><span>{l} <span class="step-arrow">→</span> {r}</span></div>'
        else:
            steps_html += f'<div class="step-item"><span style="font-size:15px;flex-shrink:0">✅</span><span>{html_lib.escape(step)}</span></div>'

    note_html = (
        f'<div class="note-box"><span class="note-label">📌 </span>{html_lib.escape(data.get("note",""))}</div>'
        if data.get("note") else ""
    )

    st.markdown(f"""
<div class="result-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <div class="result-item">{html_lib.escape(data.get("item","Item"))}</div>
      <div class="country-tag">{flag} {html_lib.escape(country.split(" ",1)[1])}
        <span class="conf-badge" style="color:{conf_color}">● {data.get("confidence","").upper()}</span>
      </div>
    </div>
    <div style="font-size:36px;margin-top:4px">{data.get("emoji", bin_info["emoji"])}</div>
  </div>
  <div class="bin-box" style="background:{bin_info['color']}18;border:1px solid {bin_info['color']}33">
    <div class="bin-label" style="color:{bin_info['color']}">PRIMARY BIN</div>
    <div class="bin-name" style="color:{bin_info['color']}">{bin_info['emoji']} {html_lib.escape(bin_info['label'])}</div>
  </div>
  <div class="steps-title">HOW TO SORT</div>
  {steps_html}
  {note_html}
</div>
""", unsafe_allow_html=True)


def process_image(image: Image.Image, country: str):
    country_code = COUNTRY_NAME_TO_CODE.get(country, "tw")
    country_display = country.split(" ", 1)[1]
    with st.spinner("🤖 Agent analyzing…"):
        prompt = (
            f"Analyze this waste item image for sorting in {country_display}. "
            f"Use the tools to identify the item and query the regulation database, "
            f"then return the JSON result."
        )
        result, steps = run_agent(prompt, country_code, image)
    st.session_state.photo_steps = steps
    return result


# ── UI ────────────────────────────────────────────────────────
st.markdown('<h1>recAIcle</h1>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">AI Agent · Waste Sorting · '
    'Point, snap, toss right.</div>',
    unsafe_allow_html=True
)

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
        "", type=["jpg","jpeg","png","webp","heic"],
        label_visibility="collapsed"
    )

    if uploaded is not None:
        new_bytes = uploaded.getvalue()
        if new_bytes and new_bytes != st.session_state.photo_bytes:
            st.session_state.photo_bytes   = new_bytes
            st.session_state.photo_result  = None
            st.session_state.photo_country = country
            st.session_state.photo_steps   = []

    if (st.session_state.photo_bytes is not None and
            st.session_state.photo_country != country):
        st.session_state.photo_result  = None
        st.session_state.photo_country = country
        st.session_state.photo_steps   = []

    if st.session_state.photo_bytes:
        image = Image.open(io.BytesIO(st.session_state.photo_bytes))
        st.image(image, use_column_width=True)

        if st.session_state.photo_result is None:
            result = process_image(image, country)
            if result:
                st.session_state.photo_result = result

        if st.session_state.photo_steps:
            render_agent_steps(st.session_state.photo_steps)

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
        country_code = COUNTRY_NAME_TO_CODE.get(country, "tw")
        country_display = country.split(" ", 1)[1]
        with st.spinner("🤖 Agent analyzing…"):
            prompt = (
                f"The user wants to sort this item in {country_display}: "
                f'"{text_query.strip()}". '
                f"Use the tools to identify and look up the regulation, "
                f"then return the JSON result."
            )
            result, steps = run_agent(prompt, country_code)
        if steps:
            render_agent_steps(steps)
        if result:
            render_result(result, country)
