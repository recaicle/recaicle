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

try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("⚠️ GEMINI_API_KEY not found in Streamlit Secrets. "
             "Go to Settings → Secrets and add: GEMINI_API_KEY = \"your_key\"")
    st.stop()
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
        "rules": """TAIWAN OFFICIAL WASTE SORTING RULES (Source: 環境部資源循環署)

RECYCLABLE (資源回收) — clean and dry items only:
- Paper: newspapers, cardboard, books, paper bags, envelopes, receipts, magazines
- Plastics: PET (#1), HDPE (#2), PP (#5) bottles and containers — must be clean
  * PET bottles: label does NOT need to be removed in Taiwan; just rinse
- Glass: bottles and jars (clean, caps removed)
- Metals: aluminum cans, steel cans (rinsed and crushed)
- Cartons/Tetra Pak: milk cartons, juice boxes (rinsed and flattened)
- Clean styrofoam (保麗龍): only if clean and dry
- Clean plastic bags and films
- Clothing, shoes, bags (clean condition)
- Used cooking oil (sealed in a bottle)
- Small electronics and e-waste, batteries, fluorescent tubes

FOOD WASTE (廚餘):
- Raw scraps (生廚餘): vegetable peels, fruit cores, eggshells, tea leaves, coffee grounds → composted
- Cooked food (熟廚餘): leftover cooked food, bones, rice, noodles → pig feed
- NOT food waste: tissues, paper towels with food on them, packaging

GENERAL WASTE (一般垃圾) — items that cannot be recycled:
- Used tissues, paper towels, toilet paper, napkins, wet wipes
- Diapers, sanitary pads, cotton swabs
- Soiled or greasy packaging (e.g. pizza box with heavy grease)
- Ceramics, dishes, cups, mirrors, non-bottle glassware
- Rubber items, leather goods, plastic toys
- Wax-coated paper, photographs, thermal receipt paper
- Cigarette butts, chewing gum, broken items of mixed materials

HAZARDOUS (有害廢棄物):
- All batteries (AA, AAA, lithium, button cells)
- Fluorescent light bulbs and tubes
- Pharmaceuticals and medicines
- Paint, solvents, pesticides, motor oil

BULKY (大型廢棄物):
- Furniture, mattresses, large home appliances
- Requires prior appointment with district office

KEY RULES:
- Recyclables must be CLEAN and DRY — soiled items go to general waste
- Tissues and paper towels are NEVER recyclable regardless of material
- Garbage trucks come at specific scheduled times; no roadside bins"""
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
        "rules": """JAPAN OFFICIAL WASTE SORTING RULES — Tokyo 23-ward standard
(Note: rules vary significantly by ward/municipality — always check local garbage calendar)

BURNABLE (燃えるゴミ) — collected 2–3× per week:
- Food scraps, fruit peels, vegetable offcuts, tea leaves, coffee grounds, bones, shells
- Tissues, paper towels, paper napkins, wax-coated paper, shredded paper, receipts
- Dirty or soiled paper that cannot be recycled
- Clothing and shoes (soiled, worn out, or non-recyclable quality)
- Rubber items, leather goods, wood scraps, chopsticks
- Small soft plastics with food residue that cannot be cleaned
- Diapers, sanitary products, cotton swabs
- Garden waste (small amounts)

NON-BURNABLE (燃えないゴミ) — collected 1–2× per month:
- Metal items UNDER 30cm: pots, pans, frying pans, cutlery, keys, tools
- Ceramics, pottery, china dishes, vases, flower pots
- Glass items (NON-bottle): drinking glasses, glass cups, window glass, mirrors
  → Wrap broken glass in newspaper and label 危険 (dangerous)
- Small electrical appliances: hair dryers, irons, electric razors, clocks, radios
- Umbrellas (collapsible type, under 30cm when folded)
- Lighters (completely emptied first)

RECYCLABLE RESOURCES (資源ゴミ) — collected on specific days by type:
- Newspapers (tied with string, separate bundle)
- Cardboard (flattened and tied with string, separate bundle)
- Magazines and books (tied with string, separate bundle)
- Glass bottles: separate by color — clear (透明), brown (茶色), other (その他); rinse, remove caps
- Aluminum cans (rinsed, crushed)
- Steel cans (rinsed)
- Clean clothing and textiles (古着・古布) — clean condition only; soiled → burnable

PET BOTTLES (ペットボトル) — separate category, collected on specific days:
- ONLY bottles with the ペットボトル mark
- Step 1: Remove cap → cap goes to burnable or charity collection box
- Step 2: Remove label → label goes to burnable
- Step 3: Rinse inside clean
- Step 4: Crush flat
- NOT included: detergent bottles, shampoo bottles, soy sauce bottles (different plastic)

OVERSIZED (粗大ゴミ):
- Any item over 30cm in any dimension
- Requires advance booking and fee payment sticker (粗大ごみ処理券)
- Home appliances (AC, TV, fridge, washing machine) → Home Appliance Recycling Law, NOT municipality

HAZARDOUS (危険ゴミ):
- Spray cans: must be COMPLETELY empty, then puncture in well-ventilated area
- Cassette gas cartridges: completely empty, puncture
- Batteries → take to collection boxes at convenience stores or supermarkets (NOT in regular trash)

PLASTICS WITH プラ MARK:
- In many Tokyo wards: separate 資源 collection day for plastic packaging with プラ mark
- If your ward does NOT collect プラ separately → rinse and put in burnable (燃えるゴミ)"""
    },

    "🇫🇷 France": {
        "bins": {
            "jaune":       {"label": "Bac Jaune Yellow Bin",        "color": "#ffe040", "emoji": "🟡"},
            "vert":        {"label": "Conteneur Verre Glass",       "color": "#40c060", "emoji": "🟢"},
            "gris":        {"label": "Bac Gris General Waste",      "color": "#aaaaaa", "emoji": "🗑️"},
            "brun":        {"label": "Bac Brun Organic",            "color": "#a05030", "emoji": "🟤"},
            "dechetterie": {"label": "Déchèterie Special Drop-off", "color": "#ff8040", "emoji": "🏭"},
        },
        "rules": """FRANCE OFFICIAL WASTE SORTING RULES (Source: ADEME)
Post-2023 extension des consignes de tri + 2024 Loi AGEC mandatory biodéchets

BAC JAUNE (Yellow bin) — ALL packaging regardless of material:
Since 2023: the golden rule is ALL packaging goes in yellow — material type no longer matters.
- ALL plastics: bottles, flasks, yogurt pots, trays, tubs, plastic bags, cling film,
  frozen food bags, bubble wrap, plastic films — ALL go in yellow
  → No need to wash — just empty them
- ALL cardboard and paper packaging: cereal boxes, shoe boxes, toilet roll tubes,
  pizza boxes (even if slightly greasy — remove food scraps first),
  newspapers, magazines, paper bags, envelopes (remove plastic windows)
  → Flatten cardboard to save space
- ALL metals: aluminum cans, steel cans and tins, aluminum foil,
  aerosol cans (ONLY if completely empty), coffee capsules, bottle caps and lids
- Cartons/Tetra Pak: milk cartons, juice bricks, soup cartons (rinse and flatten)
- NOT in yellow: tissues, paper towels, napkins, diapers → gray bin
- NOT in yellow: glass of any kind → glass container only

CONTENEUR VERRE (Green glass street container — GLASS ONLY):
- Glass bottles, jars, preserve pots, perfume bottles
- Remove lids and caps first (put caps in yellow bin)
- The glass container is a STREET-SIDE container, not a household bin
NEVER put in glass container: drinking glasses, pyrex dishes, mirrors, window glass,
ceramic, porcelain, light bulbs, crystal → these have different melting points → gray bin
⚠️ PARIS EXCEPTION: In Paris, the green bin (bac vert) is for GENERAL WASTE, not glass.
Glass in Paris goes in WHITE street containers. Check local color codes.

BAC GRIS / NOIR (Gray or black bin — non-recyclable general waste):
- Tissues, paper towels, napkins, toilet paper, wet wipes
- Diapers, sanitary products, cat litter, vacuum cleaner bags
- Ceramics, porcelain, china, dishes, mirrors, window glass, pyrex
- Extremely soiled packaging (heavily covered in grease, food, paint)
- Mixed materials that cannot be separated
- Chewing gum, cigarette butts

BAC BRUN / ORANGE (Brown/orange bin — Biodéchets organic waste):
MANDATORY since January 1, 2024 under the Loi AGEC for ALL French households.
- Food scraps: vegetable and fruit peelings, fruit cores and pits, eggshells
- Coffee grounds and paper filters, tea bags
- Bread and cooked food leftovers, meat and fish scraps, dairy products
- Small soiled cardboard pieces, paper soiled with food
- Wilted flowers (small amounts)
→ Use compostable bags or wrap in newspaper

DÉCHÈTERIE (Recycling center / special drop-off):
- Large furniture and bulky items (encombrants)
- Electronics and appliances (DEEE): computers, phones, TVs → also at retailers
- Batteries and accumulators → collection boxes at supermarkets, pharmacies
- Paint, varnish, solvents, chemicals, motor oil
- Building materials
- Textiles and clothing → dedicated STREET collection bins (Le Relais, Emmaüs)
  → Do NOT put textiles in yellow or gray bin
- Medications → return to pharmacy (pharmacie) — NEVER in any bin"""
    },
}

COUNTRY_CODE_MAP    = {"tw": "🇹🇼 Taiwan", "jp": "🇯🇵 Japan", "fr": "🇫🇷 France"}
COUNTRY_NAME_TO_CODE = {"🇹🇼 Taiwan": "tw", "🇯🇵 Japan": "jp", "🇫🇷 France": "fr"}

# ── Agentic AI Tools ──────────────────────────────────────────
TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="identify_waste_item",
            description=(
                "Step 1 — Analyze the image or text description to identify the waste item. "
                "Report its specific name, what it is made of, and whether it has multiple "
                "separable components that may need to be sorted differently."
            ),
            parameters={
                "type": "OBJECT",
                "properties": {
                    "item_name": {
                        "type": "STRING",
                        "description": "Specific English name of the item (e.g. 'used tissue', 'PET plastic bottle', 'pizza box')"
                    },
                    "description": {
                        "type": "STRING",
                        "description": "Brief description of what you see — material, condition, any special characteristics"
                    },
                    "is_composite": {
                        "type": "BOOLEAN",
                        "description": "True if the item has multiple separable components of different materials"
                    },
                    "components": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "part": {"type": "STRING"},
                                "description": {"type": "STRING"}
                            }
                        },
                        "description": "List of separable components if composite"
                    },
                    "confidence": {
                        "type": "STRING",
                        "enum": ["high", "medium", "low"]
                    }
                },
                "required": ["item_name", "description", "is_composite", "confidence"]
            }
        ),
        types.FunctionDeclaration(
            name="query_regulation_database",
            description=(
                "Step 2 — Query the official waste regulation database for a given country. "
                "Returns the FULL regulation rules so you can reason about the correct bin "
                "for the specific item identified. Always call this after identifying the item. "
                "For composite items, you may call this once and reason about all components together."
            ),
            parameters={
                "type": "OBJECT",
                "properties": {
                    "country_code": {
                        "type": "STRING",
                        "enum": ["tw", "jp", "fr"],
                        "description": "Country code: tw=Taiwan, jp=Japan, fr=France"
                    },
                    "item_name": {
                        "type": "STRING",
                        "description": "The specific item name you identified, to provide context"
                    }
                },
                "required": ["country_code", "item_name"]
            }
        ),
    ])
]


def execute_tool(name: str, args: dict, country_code: str) -> dict:
    """Execute a tool call. query_regulation_database returns full rules
    so the AI reasons about the correct bin rather than looking up a table."""

    if name == "identify_waste_item":
        return {
            "status": "identified",
            "item_name":   args.get("item_name"),
            "description": args.get("description"),
            "is_composite": args.get("is_composite", False),
            "components":  args.get("components", []),
            "confidence":  args.get("confidence", "medium"),
            "message": f"Identified: {args.get('item_name')}. Now query the regulation database."
        }

    elif name == "query_regulation_database":
        cc          = args.get("country_code", country_code)
        item        = args.get("item_name", "item")
        country_name = COUNTRY_CODE_MAP.get(cc, "🇹🇼 Taiwan")
        reg_entry   = REGULATIONS.get(country_name, REGULATIONS["🇹🇼 Taiwan"])
        rules       = reg_entry.get("rules", "")
        bins        = reg_entry.get("bins", {})

        return {
            "status":       "success",
            "country":      country_name,
            "item_queried": item,
            "regulation_rules": rules,
            "available_bins": {k: v["label"] for k, v in bins.items()},
            "source":       f"Official {country_name.split()[1]} waste regulations",
            "instruction": (
                "Read the regulation_rules carefully and reason about "
                "where EXACTLY this specific item belongs. "
                "Do not categorize by material alone — the specific item type, "
                "its condition (clean/soiled/used), and its exact form all matter. "
                "Example: 'paper' is recyclable but 'used tissue' is general waste."
            )
        }

    return {"status": "error", "message": f"Unknown tool: {name}"}


def run_agent(prompt: str, country_code: str,
              image: Image.Image = None) -> tuple:
    """
    Agentic AI loop: AI calls tools, reasons over full regulation text,
    and returns a final sorting result.
    Returns (result_dict | None, agent_steps_list)
    """
    agent_steps = []

    initial_parts = []
    if image:
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        initial_parts.append(
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
        )
    initial_parts.append(types.Part(text=prompt))

    country_name = COUNTRY_CODE_MAP.get(country_code, "🇹🇼 Taiwan")
    system_text = f"""You are an expert AI waste sorting agent for {country_name}.

Your workflow:
1. Call identify_waste_item — identify exactly what the item is (be specific: 'used tissue paper', not just 'paper').
2. Call query_regulation_database — get the official regulation rules.
3. READ the regulation rules carefully and REASON about where this specific item belongs.
   Do NOT categorize by material type alone. Consider:
   - Is it clean or soiled/used?
   - Is it a specific sub-type with special rules (e.g. tissues ≠ newspaper)?
   - Does it have multiple components that go to different bins?
4. After tool calls, respond ONLY with valid JSON (no markdown):

{{"item":"[specific item name]","bin":"[exact bin key from available_bins]","binLabel":"[label]","emoji":"[emoji]","instructions":["step 1","step 2"],"note":"[key country-specific tip]","confidence":"[high/medium/low]"}}

For composite items, use "[Part]: [prep] → [bin name]" format in instructions."""

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

        content  = response.candidates[0].content
        fn_calls = [p for p in content.parts
                    if hasattr(p, "function_call") and p.function_call
                    and p.function_call.name]

        if not fn_calls:
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

        messages.append(content)
        fn_response_parts = []

        for part in content.parts:
            if not (hasattr(part, "function_call") and part.function_call
                    and part.function_call.name):
                continue
            fc     = part.function_call
            args   = dict(fc.args) if fc.args else {}
            result = execute_tool(fc.name, args, country_code)

            if fc.name == "identify_waste_item":
                detail = (
                    f"{args.get('item_name','?')} · "
                    f"{args.get('confidence','?').upper()} confidence"
                )
                if args.get("is_composite"):
                    comps  = ", ".join(c.get("part","?") for c in args.get("components",[])[:4])
                    detail += f" · Parts: {comps}"
                label = "🔍 Identified item"
            elif fc.name == "query_regulation_database":
                detail = f"Queried {COUNTRY_CODE_MAP.get(args.get('country_code','tw'),'?')} rules for: {args.get('item_name','?')}"
                label  = "📋 Queried regulation database"
            else:
                detail = str(args)
                label  = f"🔧 {fc.name}"

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
.stExpander {
    background: #071209 !important; border: 1px solid #1e3622 !important;
    border-radius: 12px !important;
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
    padding:10px 14px; margin-bottom:8px; font-size:13px; color:#7a9e82; line-height:1.6;
}
.agent-step-label { color:#4dff91; font-weight:600; margin-bottom:2px; font-size:12px; }
[data-testid="stSelectbox"] > div {
    background:#071209 !important; border:1px solid #1e3622 !important;
    border-radius:12px !important; color:#e8f5eb !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
for key, val in {
    "photo_bytes": None, "photo_result": None,
    "photo_country": None, "photo_steps": []
}.items():
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
    reg      = REGULATIONS.get(country, REGULATIONS["🇹🇼 Taiwan"])
    bin_key  = data.get("bin", "general")
    bin_info = reg["bins"].get(bin_key, {
        "label": data.get("binLabel", "?"), "color": "#4dff91", "emoji": "♻️"
    })
    conf_colors = {"high": "#4dff91", "medium": "#ffe040", "low": "#ff9090"}
    conf_color  = conf_colors.get(data.get("confidence", "high"), "#4dff91")
    flag = country.split()[0]

    steps_html = ""
    for step in data.get("instructions", []):
        if "→" in step:
            parts = step.split("→", 1)
            l = html_lib.escape(parts[0].strip())
            r = html_lib.escape(parts[1].strip())
            steps_html += (
                f'<div class="step-item composite">'
                f'<span style="font-size:15px;flex-shrink:0">🔧</span>'
                f'<span>{l} <span class="step-arrow">→</span> {r}</span></div>'
            )
        else:
            steps_html += (
                f'<div class="step-item">'
                f'<span style="font-size:15px;flex-shrink:0">✅</span>'
                f'<span>{html_lib.escape(step)}</span></div>'
            )

    note_html = (
        f'<div class="note-box"><span class="note-label">📌 </span>'
        f'{html_lib.escape(data.get("note", ""))}</div>'
        if data.get("note") else ""
    )

    st.markdown(f"""
<div class="result-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <div class="result-item">{html_lib.escape(data.get("item","Item"))}</div>
      <div class="country-tag">{flag} {html_lib.escape(country.split(" ",1)[1])}
        <span class="conf-badge" style="color:{conf_color}">
          ● {data.get("confidence","").upper()}</span>
      </div>
    </div>
    <div style="font-size:36px;margin-top:4px">{data.get("emoji", bin_info["emoji"])}</div>
  </div>
  <div class="bin-box"
       style="background:{bin_info['color']}18;border:1px solid {bin_info['color']}33">
    <div class="bin-label" style="color:{bin_info['color']}">PRIMARY BIN</div>
    <div class="bin-name" style="color:{bin_info['color']}">
      {bin_info['emoji']} {html_lib.escape(bin_info['label'])}</div>
  </div>
  <div class="steps-title">HOW TO SORT</div>
  {steps_html}
  {note_html}
</div>
""", unsafe_allow_html=True)


def process_image(image: Image.Image, country: str):
    country_code    = COUNTRY_NAME_TO_CODE.get(country, "tw")
    country_display = country.split(" ", 1)[1]
    with st.spinner("🤖 Agent analyzing…"):
        prompt = (
            f"Analyze this waste item image for sorting in {country_display}. "
            f"First identify exactly what the item is (be specific), "
            f"then query the regulation database and reason carefully about "
            f"which bin it belongs to. Return the JSON result."
        )
        result, steps = run_agent(prompt, country_code, image)
    st.session_state.photo_steps = steps
    return result


# ── UI ────────────────────────────────────────────────────────
st.markdown('<h1>recAIcle</h1>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">AI Agent · Waste Sorting · Point, snap, toss right.</div>',
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
        "", type=["jpg", "jpeg", "png", "webp", "heic"],
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
            "", placeholder="e.g. used tissue, pizza box, PET bottle...",
            label_visibility="collapsed"
        )
    with col2:
        ask_btn = st.button("Ask AI", type="primary", use_container_width=True)

    if ask_btn and text_query.strip():
        country_code    = COUNTRY_NAME_TO_CODE.get(country, "tw")
        country_display = country.split(" ", 1)[1]
        with st.spinner("🤖 Agent analyzing…"):
            prompt = (
                f"The user wants to sort this item in {country_display}: "
                f'"{text_query.strip()}". '
                f"Identify it specifically, query the regulation database, "
                f"reason carefully about which bin it belongs to, "
                f"then return the JSON result."
            )
            result, steps = run_agent(prompt, country_code)
        if steps:
            render_agent_steps(steps)
        if result:
            render_result(result, country)
