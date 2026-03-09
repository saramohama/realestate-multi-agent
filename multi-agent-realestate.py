from flask import Flask, request, jsonify, render_template
import anthropic
import json
import os
from datetime import datetime

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ─────────────────────────────────────────────
# SHARED MEMORY (conversations per session)
# ─────────────────────────────────────────────

conversations: dict = {}

# ─────────────────────────────────────────────
# TOOL IMPLEMENTATIONS (shared across agents)
# ─────────────────────────────────────────────

def save_listing(owner_name, address, property_type, bedrooms, bathrooms, sqft, price, description):
    listing = {
        "listing_id": "LST-" + datetime.now().strftime("%Y%m%d%H%M%S"),
        "owner_name": owner_name,
        "address": address,
        "property_type": property_type,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "sqft": sqft,
        "price": price,
        "description": description,
        "status": "active",
        "listed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _append_json("listings.json", listing)
    return f"Listing saved! ID: {listing['listing_id']} — {address} listed at {price}"


def search_listings(property_type=None, max_price=None, min_bedrooms=None, location=None):
    try:
        with open("listings.json", "r") as f:
            all_listings = json.load(f)
    except FileNotFoundError:
        return "No listings found yet."
    results = [l for l in all_listings if l.get("status") == "active"]
    if property_type:
        results = [l for l in results if property_type.lower() in l.get("property_type", "").lower()]
    if max_price:
        try:
            results = [l for l in results if float(str(l.get("price","0")).replace("$","").replace(",","")) <= float(max_price)]
        except ValueError:
            pass
    if min_bedrooms:
        try:
            results = [l for l in results if int(l.get("bedrooms", 0)) >= int(min_bedrooms)]
        except ValueError:
            pass
    if location:
        results = [l for l in results if location.lower() in l.get("address", "").lower()]
    if not results:
        return "No listings match your criteria."
    lines = [f"Found {len(results)} listing(s):"]
    for l in results[:5]:
        lines.append(f"- [{l['listing_id']}] {l['address']} | {l['property_type']} | {l['bedrooms']}bd/{l['bathrooms']}ba | {l['sqft']} sqft | {l['price']}")
    return "\n".join(lines)


def schedule_viewing(client_name, property_address, preferred_datetime, phone):
    viewing = {
        "viewing_id": "VW-" + datetime.now().strftime("%Y%m%d%H%M%S"),
        "client_name": client_name,
        "property_address": property_address,
        "preferred_datetime": preferred_datetime,
        "phone": phone,
        "status": "scheduled",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _append_json("viewings.json", viewing)
    return f"Viewing scheduled! ID: {viewing['viewing_id']} — {client_name} will visit {property_address} on {preferred_datetime}."


def calculate_mortgage(property_price, down_payment, loan_term_years, annual_interest_rate=7.0):
    try:
        price = float(str(property_price).replace("$","").replace(",",""))
        down  = float(str(down_payment).replace("$","").replace(",",""))
        term  = int(loan_term_years)
        rate  = float(annual_interest_rate)
        principal = price - down
        monthly_rate = rate / 100 / 12
        n = term * 12
        monthly = principal * (monthly_rate * (1 + monthly_rate)**n) / ((1 + monthly_rate)**n - 1) if monthly_rate else principal / n
        total_paid = monthly * n
        return (f"Mortgage Estimate:\n"
                f"  Price: ${price:,.2f} | Down: ${down:,.2f} | Loan: ${principal:,.2f}\n"
                f"  Rate: {rate}% | Term: {term} years\n"
                f"  Monthly Payment: ${monthly:,.2f}\n"
                f"  Total Interest: ${total_paid - principal:,.2f} | Total Cost: ${total_paid + down:,.2f}")
    except Exception as e:
        return f"Could not calculate: {str(e)}"


def _append_json(filename, record):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    data.append(record)
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────
# SPECIALIZED SUB-AGENTS
# ─────────────────────────────────────────────

def run_agent(system_prompt, tools, tool_map, messages):
    """Generic agent loop — runs until end_turn."""
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system_prompt,
            tools=tools if tools else [],
            messages=messages,
        )
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    fn = tool_map.get(block.name)
                    result = fn(**block.input) if fn else f"Unknown tool: {block.name}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            reply = next((b.text for b in response.content if hasattr(b, "text")), "")
            return reply


# ── LISTING AGENT ──
LISTING_SYSTEM = """
You are Lisa, a specialist real estate listing agent.
Your ONLY job: help owners list properties and help buyers search listings.
Keep replies short and professional. No markdown.
Collect all details before saving: owner name, address, type, beds, baths, sqft, price, description.
"""

LISTING_TOOLS = [
    {
        "name": "save_listing",
        "description": "Save a new property listing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner_name":    {"type": "string"},
                "address":       {"type": "string"},
                "property_type": {"type": "string"},
                "bedrooms":      {"type": "string"},
                "bathrooms":     {"type": "string"},
                "sqft":          {"type": "string"},
                "price":         {"type": "string"},
                "description":   {"type": "string"},
            },
            "required": ["owner_name","address","property_type","bedrooms","bathrooms","sqft","price","description"],
        },
    },
    {
        "name": "search_listings",
        "description": "Search active listings by filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string"},
                "max_price":     {"type": "string"},
                "min_bedrooms":  {"type": "string"},
                "location":      {"type": "string"},
            },
            "required": [],
        },
    },
]

LISTING_TOOL_MAP = {"save_listing": save_listing, "search_listings": search_listings}


# ── MORTGAGE AGENT ──
MORTGAGE_SYSTEM = """
You are Max, a mortgage calculation specialist.
Your ONLY job: calculate mortgage estimates for clients.
Keep replies short. No markdown.
Always collect: property price, down payment, loan term (years), interest rate (default 7%).
After calculating, ask if they want to try different numbers.
"""

MORTGAGE_TOOLS = [
    {
        "name": "calculate_mortgage",
        "description": "Calculate estimated monthly mortgage payment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_price":       {"type": "string"},
                "down_payment":         {"type": "string"},
                "loan_term_years":      {"type": "string"},
                "annual_interest_rate": {"type": "string"},
            },
            "required": ["property_price", "down_payment", "loan_term_years"],
        },
    }
]

MORTGAGE_TOOL_MAP = {"calculate_mortgage": calculate_mortgage}


# ── VIEWING AGENT ──
VIEWING_SYSTEM = """
You are Vera, a property viewing scheduler.
Your ONLY job: schedule property viewings for clients.
Keep replies short. No markdown.
Collect: client name, property address or listing ID, preferred date/time, phone number.
"""

VIEWING_TOOLS = [
    {
        "name": "schedule_viewing",
        "description": "Schedule a property viewing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name":        {"type": "string"},
                "property_address":   {"type": "string"},
                "preferred_datetime": {"type": "string"},
                "phone":              {"type": "string"},
            },
            "required": ["client_name", "property_address", "preferred_datetime", "phone"],
        },
    }
]

VIEWING_TOOL_MAP = {"schedule_viewing": schedule_viewing}


# ─────────────────────────────────────────────
# ORCHESTRATOR AGENT
# ─────────────────────────────────────────────

ORCHESTRATOR_SYSTEM = """
You are Alex, the main coordinator for Prestige Realty Group.
You manage a team of specialist agents:

  - LISTING AGENT (Lisa): lists properties, searches listings
  - MORTGAGE AGENT (Max): calculates mortgage estimates
  - VIEWING AGENT (Vera): schedules property viewings

Your job:
1. Greet the user warmly on first message.
2. Understand what they need.
3. Decide which specialist agent to route to.
4. Call the appropriate routing tool.
5. If the request is general (greetings, questions about the agency), answer directly.

Always be warm, professional, and concise. No markdown.

Agency: Prestige Realty Group | 456 Park Ave, NY | 555-9000 | Mon-Fri 9am-6pm
"""

ORCHESTRATOR_TOOLS = [
    {
        "name": "route_to_listing_agent",
        "description": "Route to Lisa the listing specialist — for listing a property or searching listings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_message": {"type": "string", "description": "The user's message to pass to the listing agent"},
                "context":      {"type": "string", "description": "Any helpful context summary for the agent"},
            },
            "required": ["user_message"],
        },
    },
    {
        "name": "route_to_mortgage_agent",
        "description": "Route to Max the mortgage specialist — for mortgage calculations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_message": {"type": "string", "description": "The user's message to pass to the mortgage agent"},
                "context":      {"type": "string", "description": "Any helpful context summary for the agent"},
            },
            "required": ["user_message"],
        },
    },
    {
        "name": "route_to_viewing_agent",
        "description": "Route to Vera the viewing specialist — for scheduling property viewings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_message": {"type": "string", "description": "The user's message to pass to the viewing agent"},
                "context":      {"type": "string", "description": "Any helpful context summary for the agent"},
            },
            "required": ["user_message"],
        },
    },
]


# ─────────────────────────────────────────────
# ROUTING FUNCTIONS (called by orchestrator)
# ─────────────────────────────────────────────

def route_to_listing_agent(user_message, context="", session_id="default"):
    key = f"{session_id}_listing"
    if key not in conversations:
        conversations[key] = []
    conversations[key].append({"role": "user", "content": user_message})
    reply = run_agent(LISTING_SYSTEM, LISTING_TOOLS, LISTING_TOOL_MAP, conversations[key])
    conversations[key].append({"role": "assistant", "content": reply})
    return f"[Lisa - Listing Specialist]: {reply}"


def route_to_mortgage_agent(user_message, context="", session_id="default"):
    key = f"{session_id}_mortgage"
    if key not in conversations:
        conversations[key] = []
    conversations[key].append({"role": "user", "content": user_message})
    reply = run_agent(MORTGAGE_SYSTEM, MORTGAGE_TOOLS, MORTGAGE_TOOL_MAP, conversations[key])
    conversations[key].append({"role": "assistant", "content": reply})
    return f"[Max - Mortgage Specialist]: {reply}"


def route_to_viewing_agent(user_message, context="", session_id="default"):
    key = f"{session_id}_viewing"
    if key not in conversations:
        conversations[key] = []
    conversations[key].append({"role": "user", "content": user_message})
    reply = run_agent(VIEWING_SYSTEM, VIEWING_TOOLS, VIEWING_TOOL_MAP, conversations[key])
    conversations[key].append({"role": "assistant", "content": reply})
    return f"[Vera - Viewing Specialist]: {reply}"


# ─────────────────────────────────────────────
# MAIN ORCHESTRATOR LOOP
# ─────────────────────────────────────────────

def get_orchestrator_reply(session_id: str, user_message: str) -> str:
    key = f"{session_id}_orchestrator"
    if key not in conversations:
        conversations[key] = []

    conversations[key].append({"role": "user", "content": user_message})

    # Build routing tool map with session_id closure
    routing_map = {
        "route_to_listing_agent":  lambda **kw: route_to_listing_agent(**kw, session_id=session_id),
        "route_to_mortgage_agent": lambda **kw: route_to_mortgage_agent(**kw, session_id=session_id),
        "route_to_viewing_agent":  lambda **kw: route_to_viewing_agent(**kw, session_id=session_id),
    }

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=ORCHESTRATOR_SYSTEM,
            tools=ORCHESTRATOR_TOOLS,
            messages=conversations[key],
        )

        if response.stop_reason == "tool_use":
            conversations[key].append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    fn = routing_map.get(block.name)
                    result = fn(**block.input) if fn else f"Unknown route: {block.name}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            conversations[key].append({"role": "user", "content": tool_results})
        else:
            reply = next((b.text for b in response.content if hasattr(b, "text")), "")
            conversations[key].append({"role": "assistant", "content": reply})
            return reply


# ─────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    session_id = body.get("session_id", "default")
    message    = body.get("message", "")
    if not message:
        return jsonify({"error": "message is required"}), 400
    reply = get_orchestrator_reply(session_id, message)
    return jsonify({"reply": reply, "session_id": session_id})


@app.route("/listings", methods=["GET"])
def list_all():
    try:
        with open("listings.json", "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify([])


@app.route("/viewings", methods=["GET"])
def list_viewings():
    try:
        with open("viewings.json", "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify([])


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "system": "Multi-Agent Real Estate System",
        "agents": ["Orchestrator (Alex)", "Listing (Lisa)", "Mortgage (Max)", "Viewing (Vera)"]
    })


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Multi-Agent Real Estate System running on http://localhost:5000")
    print("Agents: Alex (Orchestrator) → Lisa (Listing) | Max (Mortgage) | Vera (Viewing)")
    print("Endpoints:")
    print("  POST /chat     — talk to the orchestrator")
    print("  GET  /listings — view all listings")
    print("  GET  /viewings — view all viewings")
    print("  GET  /health   — system status")
    app.run(debug=False, port=5000)
