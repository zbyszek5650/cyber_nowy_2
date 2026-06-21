import streamlit as st
import pandas as pd
import datetime
import time
import yaml
import os
import base64
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go

# =====================================================================================
#  CRISIS SIMULATION ENGINE  ::  v3.0
#  Bazuje na v2.0 (Breaking News, Archiwum Decyzji, God Mode, optymalizacja timera
#  przez st.fragment). NOWE FILARY v3.0:
#   1) FILAR FINANSOWY  - Giełda / "Kurs Akcji" spółki (terminal giełdowy, plotly)
#   2) FILAR CYBER      - Sklep z raportami wywiadowczymi (OSINT Threat Intel Shop)
#   3) GAMIFIKACJA #1   - Celowane Wrzutki (Targeted Injects) + integracja z God Mode
#   4) GAMIFIKACJA #2   - Debriefing 2.0: Wykres Radarowy + System Odznak (Tytuły)
#
#  ZASADY ZACHOWANE:
#   - Styl Dark Mode / Cyberpunk (CSS bez zmian + nowe, spójne klasy)
#   - @st.cache_resource jako globalny silnik multiplayer
#   - @st.fragment, aby nowe mechaniki nie przeładowywały całej strony (timer!)
# =====================================================================================

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Crisis Simulation Engine",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# --- ENGINE (GLOBALNA SYNCHRONIZACJA MULTIPLAYER) ---
@st.cache_resource
def get_global_engine():
    return {
        "config": None,                 # Dane game_config z pliku YAML
        "scenarios": [],                # Lista scenariuszy z pliku YAML
        "scenario_idx": 0,
        "round": 0,
        "teams": {},
        "status": "NO_CONFIG",          # NO_CONFIG -> ACTIVE -> FINISHED
        "round_start_time": None,       # Czas startu dla timera
        # --- KLUCZE v3.2 (przerwa między scenariuszami) ---
        "intermission": False,          # v3.2: czy gra jest w stanie "przerwy" przed kolejnym scenariuszem?
        "last_round_summary": None,     # v3.2: podsumowanie ostatnio ocenionej rundy (passed/eliminated)
        # --- KLUCZE v2 ---
        "broadcast_msg": "",            # Najnowszy komunikat alarmowy od Admina
        "broadcast_id": 0,              # Inkrementowany identyfikator (do wykrywania nowości / toast)
        "broadcast_target": "ALL",      # NOWE v3: "ALL" lub nazwa konkretnego zespołu (Targeted Inject)
        "broadcast_history": [],        # Lista poprzednich komunikatów [{ "id", "time", "text", "target" }]
        "manual_score_adjustments": {}  # { team_name: { metric_id: delta_skumulowana } } (God Mode + OSINT)
    }

state = get_global_engine()

# --- STRUKTURA POJEDYNCZEGO ZESPOŁU (z polami v3.0 / v3.1) ---
def new_team_record():
    return {
        "decisions": {},
        "ready": False,
        "stock_history": [],        # v3: [{ "label", "scenario", "round", "price" }]
        "osint_purchased": [],      # v3: lista kluczy "s_idx_r_num" z zakupionym raportem
        "is_eliminated": False,     # v3.1: czy zespół oblał warunek przejścia rundy?
        "eliminated_in_round": None,  # v3.1: numer rundy, w której zespół odpadł
        "eliminated_in_scenario": None,  # v3.1: indeks scenariusza eliminacji
        "eliminated_reason": None   # v3.2: powód eliminacji (np. "kurs akcji 42.0 < 50.0" lub "Budżet = 0")
    }

def ensure_team_fields(team_data):
    """Uzupełnia rekord zespołu o pola v3.0 / v3.1 (kompatybilność wstecz)."""
    team_data.setdefault("decisions", {})
    team_data.setdefault("ready", False)
    team_data.setdefault("stock_history", [])
    team_data.setdefault("osint_purchased", [])
    team_data.setdefault("is_eliminated", False)
    team_data.setdefault("eliminated_in_round", None)
    team_data.setdefault("eliminated_in_scenario", None)
    team_data.setdefault("eliminated_reason", None)
    return team_data

# --- FUNKCJA DO POBRANIA LOKALNEGO LOGO ---
def get_image_as_base64(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- DYNAMICZNY ZAPIS BRANDINGU I KOLORÓW ---
bg_color = "#0f172a"
panel_bg = "#1e293b"
text_primary = "#f8fafc"
text_secondary = "#94a3b8"
accent_primary = "#06b6d4"
accent_red = "#ef4444"
accent_green = "#22c55e"
logo_url = ""

if state["config"] and "branding" in state["config"]:
    b = state["config"]["branding"]
    bg_color = b.get("background_color", bg_color)
    panel_bg = b.get("panel_bg_color", panel_bg)
    text_primary = b.get("text_color", text_primary)
    accent_primary = b.get("primary_color", accent_primary)
    # Obsługa URL lub lokalnego pliku
    raw_logo = b.get("logo_url", "")
    if raw_logo.endswith(".png") or raw_logo.endswith(".jpg"):
        if not raw_logo.startswith("http"):
            b64 = get_image_as_base64(raw_logo)
            logo_url = f"data:image/png;base64,{b64}" if b64 else ""
        else:
            logo_url = raw_logo
    else:
        logo_url = raw_logo

# --- BEZPIECZNY, JEDNOLINJKOWY CSS (rozszerzony o klasy v3.0) ---
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
:root {{
    --bg-color: {bg_color}; --panel-bg: {panel_bg}; --border-color: #334155;
    --text-primary: {text_primary}; --text-secondary: {text_secondary};
    --accent-cyan: {accent_primary}; --accent-red: {accent_red};
    --accent-green: {accent_green}; --accent-yellow: #f59e0b;
    --font-sans: 'Inter', sans-serif; --font-mono: 'JetBrains Mono', monospace;
}}
.stApp {{ background-color: var(--bg-color) !important; color: var(--text-primary); font-family: var(--font-sans); }}
#MainMenu, footer, header {{ visibility: hidden; }}
.command-header {{ height: 64px; background: rgba(15, 23, 42, 0.8); border-bottom: 1px solid var(--border-color); padding: 0 24px; display: flex; justify-content: space-between; align-items: center; margin-top: -75px; margin-bottom: 24px; position: sticky; top: 0; z-index: 1000; }}
.brand-container {{ display: flex; align-items: center; gap: 12px; }}
.brand-logo {{ max-height: 35px; object-fit: contain; }}
.brand-title {{ font-family: var(--font-mono); font-weight: 700; font-size: 1.2rem; color: var(--accent-cyan); text-transform: uppercase; }}
.status-badge {{ background: rgba(239, 68, 68, 0.2); border: 1px solid var(--accent-red); color: var(--accent-red); padding: 4px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }}
.panel {{ background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 6px; padding: 16px; height: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
.panel-label {{ font-size: 0.7rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; margin-bottom: 12px; display: block; }}
.kpi-header {{ display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 6px; }}
.progress-bar-bg {{ background: var(--bg-color); height: 4px; border-radius: 2px; overflow: hidden; }}
.progress-bar-fill {{ height: 100%; transition: width 1s; background: var(--accent-cyan); }}
.scenario-header {{ background: linear-gradient(135deg, var(--panel-bg) 0%, var(--bg-color) 100%); border-left: 4px solid var(--accent-cyan); padding: 20px; margin-bottom: 20px; }}
.danger-zone {{ border: 1px solid var(--accent-red); padding: 15px; border-radius: 6px; margin-top: 20px; background: rgba(239, 68, 68, 0.05); }}
.broadcast-bar {{ border: 1px solid var(--accent-red); border-left: 5px solid var(--accent-yellow); background: linear-gradient(90deg, rgba(239, 68, 68, 0.18) 0%, rgba(245, 158, 11, 0.10) 100%); padding: 14px 18px; border-radius: 6px; margin-bottom: 18px; animation: pulseAlarm 2.2s infinite; }}
.broadcast-bar .bc-label {{ color: var(--accent-yellow); font-family: var(--font-mono); font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; display: block; margin-bottom: 4px; }}
.broadcast-bar .bc-text {{ color: var(--text-primary); font-size: 1rem; font-weight: 600; }}
@keyframes pulseAlarm {{ 0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.35); }} 70% {{ box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }} }}
.archive-item {{ border-left: 2px solid var(--accent-cyan); padding: 6px 10px; margin-bottom: 8px; background: rgba(6, 182, 212, 0.05); border-radius: 0 4px 4px 0; }}
.archive-item .ai-meta {{ font-family: var(--font-mono); font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase; }}
.archive-item .ai-choice {{ font-size: 0.82rem; color: var(--text-primary); }}
.god-readout {{ font-family: var(--font-mono); font-size: 0.8rem; color: var(--accent-yellow); }}
.ticker-bar {{ display: flex; justify-content: space-between; align-items: baseline; background: #0a0f1d; border: 1px solid var(--border-color); border-radius: 6px 6px 0 0; padding: 10px 16px; font-family: var(--font-mono); }}
.ticker-bar .tk-sym {{ color: var(--text-secondary); font-size: 0.72rem; letter-spacing: 1px; text-transform: uppercase; }}
.ticker-bar .tk-price {{ font-size: 1.5rem; font-weight: 700; }}
.ticker-bar .tk-up {{ color: var(--accent-green); }}
.ticker-bar .tk-down {{ color: var(--accent-red); }}
.osint-box {{ border: 1px solid var(--accent-green); border-left: 5px solid var(--accent-green); background: rgba(34, 197, 94, 0.08); padding: 14px 18px; border-radius: 6px; margin: 14px 0; font-family: var(--font-mono); }}
.osint-box .ob-label {{ color: var(--accent-green); font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; display: block; margin-bottom: 6px; }}
.osint-box .ob-text {{ color: var(--text-primary); font-size: 0.92rem; line-height: 1.5; }}
.badge-card {{ border: 1px solid var(--accent-yellow); border-radius: 8px; padding: 16px; margin-bottom: 12px; background: linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(15, 23, 42, 0.2) 100%); box-shadow: 0 0 14px rgba(245, 158, 11, 0.15); }}
.badge-card .bd-icon {{ font-size: 1.8rem; }}
.badge-card .bd-title {{ font-family: var(--font-mono); font-weight: 700; color: var(--accent-yellow); font-size: 1.05rem; text-transform: uppercase; letter-spacing: 1px; }}
.badge-card .bd-desc {{ color: var(--text-secondary); font-size: 0.8rem; }}
.debrief-hero {{ background: linear-gradient(135deg, var(--panel-bg) 0%, var(--bg-color) 100%); border-left: 4px solid var(--accent-yellow); padding: 22px; margin-bottom: 20px; border-radius: 0 6px 6px 0; }}
.stButton > button {{ background: var(--accent-cyan) !important; color: #000 !important; font-weight: 700 !important; border: none !important; border-radius: 4px !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; padding: 14px !important; transition: all 0.2s ease !important; }}
.stButton > button:hover {{ opacity: 0.9 !important; box-shadow: 0 0 12px rgba(6, 182, 212, 0.3) !important; }}
.stRadio label {{ background: #2d3748 !important; border: 1px solid var(--border-color) !important; color: var(--text-primary) !important; padding: 12px 16px !important; border-radius: 4px !important; font-size: 0.85rem !important; margin-bottom: 8px !important; }}
.stRadio div[role="radiogroup"] > label:hover {{ border-color: var(--accent-cyan) !important; background: rgba(6, 182, 212, 0.05) !important; }}
</style>""", unsafe_allow_html=True)

# --- BEZPIECZNY KOMPONENT NAGŁÓWKA ---
def render_header(suffix=""):
    title = state["config"]["title"] if state["config"] else "Crisis Engine"
    logo_html = f'<img src="{logo_url}" class="brand-logo">' if logo_url else ''
    st.markdown(f'<div class="command-header"><div class="brand-container">{logo_html}<div class="brand-title">{title} // {suffix}</div></div></div>', unsafe_allow_html=True)

# --- FUNKCJA ŁADOWANIA PLIKU YAML ---
def load_yaml_config(file):
    try:
        data = yaml.safe_load(file)
        state["config"] = data.get("game_config", {})
        state["scenarios"] = data.get("scenarios", [])
        state["scenario_idx"] = 0
        state["round"] = 0
        state["teams"] = {}
        state["status"] = "ACTIVE"
        # Reset funkcji v2/v3 przy nowym wgraniu konfiguracji
        state["intermission"] = False
        state["last_round_summary"] = None
        state["broadcast_msg"] = ""
        state["broadcast_id"] = 0
        state["broadcast_target"] = "ALL"
        state["broadcast_history"] = []
        state["manual_score_adjustments"] = {}

        # --- v3.1: WALIDACJA LICZBY OPCJI (wymagane 3-4 na pytanie) ---
        validation_warnings = []
        for scen in state["scenarios"]:
            for r_num, r_data in (scen.get("rounds", {}) or {}).items():
                for q_name, q_data in (r_data.get("questions", {}) or {}).items():
                    opt_count = len((q_data or {}).get("options", {}) or {})
                    if opt_count < 3 or opt_count > 4:
                        validation_warnings.append(
                            f"⚠️ Scenariusz '{scen.get('name', scen.get('id', '?'))}', "
                            f"runda {r_num}, pytanie '{q_name}': {opt_count} opcji (wymagane 3-4)."
                        )
        for w in validation_warnings:
            st.warning(w)

        st.success("Plik YAML zweryfikowany i wgrany do pamięci globalnej!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Błąd struktury pliku YAML: {e}")

# --- BROADCAST: ZAPIS NOWEGO KOMUNIKATU (z obsługą celowanych wrzutek v3) ---
def push_broadcast(text, target="ALL", adjustments=None):
    """Nadaje komunikat do wszystkich lub do konkretnego zespołu.
    adjustments: dict {metric_id: delta} -> opcjonalna kara/nagroda God Mode."""
    text = (text or "").strip()
    if not text:
        return False

    # Archiwizacja poprzedniego komunikatu
    if state.get("broadcast_msg"):
        state.setdefault("broadcast_history", []).append({
            "id": state.get("broadcast_id", 0),
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "text": state["broadcast_msg"],
            "target": state.get("broadcast_target", "ALL")
        })

    state["broadcast_id"] = state.get("broadcast_id", 0) + 1
    state["broadcast_msg"] = text
    state["broadcast_target"] = target or "ALL"

    # Integracja z God Mode - nałożenie kary/nagrody wraz z komunikatem
    if adjustments:
        targets = list(state["teams"].keys()) if target == "ALL" else [target]
        for tname in targets:
            if tname not in state["teams"]:
                continue
            adj = state.setdefault("manual_score_adjustments", {}).setdefault(tname, {})
            for metric_id, delta in adjustments.items():
                if delta:
                    adj[metric_id] = adj.get(metric_id, 0) + int(delta)
    return True

# =====================================================================================
#  HELPERY v3.0  ::  METRYKI / GIEŁDA / ROLE / ODZNAKI / WYKRESY
# =====================================================================================

def hex_to_rgba(hex_color, alpha=1.0):
    """Konwersja #rrggbb -> 'rgba(r,g,b,a)' (na potrzeby wypełnień plotly)."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return f"rgba(6,182,212,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def get_gamification_cfg():
    cfg = state.get("config") or {}
    return cfg.get("gamification", {}) or {}

def get_metric_ids():
    cfg = state.get("config") or {}
    return [m["id"] for m in cfg.get("metrics", [])]

def get_metric_label(metric_id):
    cfg = state.get("config") or {}
    for m in cfg.get("metrics", []):
        if m["id"] == metric_id:
            return m["label"]
    return metric_id

def calculate_metrics_dict(team_name):
    """Zwraca {metric_id: wartość 0..150} z uwzględnieniem decyzji + korekt (God Mode/OSINT)."""
    config = state["config"]
    scenarios = state["scenarios"]
    if not config or not scenarios:
        return {}

    metric_ids = get_metric_ids()
    scores = {mid: 100 for mid in metric_ids}
    team = state["teams"].get(team_name, {})

    # 1) Wpływ decyzji podjętych w rundach
    for s_idx_str, r_decs in team.get("decisions", {}).items():
        s_idx = int(s_idx_str)
        for r_num_str, roles in r_decs.items():
            r_num = int(r_num_str)
            if s_idx < len(scenarios):
                scen = scenarios[s_idx]
                rd = scen.get("rounds", {}).get(r_num) or scen.get("rounds", {}).get(str(r_num))
                if rd:
                    for role, choice in roles.items():
                        options = rd.get("questions", {}).get(role, {}).get("options", {})
                        if choice in options:
                            impact = options[choice]
                            for metric_id, val in impact.items():
                                if metric_id in scores:
                                    scores[metric_id] += val

    # 2) Ręczne korekty Trenera (God Mode) + opłaty OSINT - trwale w stanie globalnym
    adjustments = state.get("manual_score_adjustments", {}).get(team_name, {})
    for metric_id, delta in adjustments.items():
        if metric_id in scores:
            scores[metric_id] += delta

    return {mid: max(0, min(150, scores[mid])) for mid in metric_ids}

def calculate_metrics(team_name):
    """Kompatybilność wstecz: lista wartości w kolejności metryk z configu."""
    d = calculate_metrics_dict(team_name)
    return [d.get(mid, 100) for mid in get_metric_ids()]

def _find_metric_by_keywords(keywords):
    cfg = state.get("config") or {}
    for m in cfg.get("metrics", []):
        haystack = f"{m.get('id','')} {m.get('label','')}".lower()
        if any(k in haystack for k in keywords):
            return m["id"]
    return None

def get_role_map():
    """Mapuje role semantyczne -> id metryk. Najpierw config.gamification.roles,
    w razie braku heurystyka po nazwach metryk."""
    metric_ids = get_metric_ids()
    cfg_roles = get_gamification_cfg().get("roles", {}) or {}

    def resolve(role, keywords):
        rid = cfg_roles.get(role)
        if rid in metric_ids:
            return rid
        return _find_metric_by_keywords(keywords)

    return {
        "liquidity": resolve("liquidity", ["budz", "budżet", "budget", "płynn", "plynn", "finans", "cash", "skarb", "kapita", "money"]),
        "security": resolve("security", ["uptime", "dostęp", "dostep", "cyber", "bezpiecz", "security", "zgodn", "compliance", "forteca", "uptim"]),
        "reputation": resolve("reputation", ["pr", "zaufan", "wizerun", "reputation", "media", "image", "trust", "iluzj"]),
    }

def get_stock_weights():
    """Zwraca znormalizowane wagi {metric_id: w} sumujące się do 1.0."""
    metric_ids = get_metric_ids()
    raw = get_gamification_cfg().get("stock_weights", {}) or {}
    weights = {mid: float(w) for mid, w in raw.items() if mid in metric_ids and float(w) > 0}

    # Fallback: domyślne wagi w oparciu o mapę ról (50% reputacja / 30% płynność / 20% bezp.)
    if not weights:
        role_map = get_role_map()
        defaults = {role_map.get("reputation"): 0.5, role_map.get("liquidity"): 0.3, role_map.get("security"): 0.2}
        weights = {mid: w for mid, w in defaults.items() if mid in metric_ids}

    # Ostateczny fallback: równe wagi na wszystkie metryki
    if not weights and metric_ids:
        weights = {mid: 1.0 for mid in metric_ids}

    total = sum(weights.values()) or 1.0
    return {mid: w / total for mid, w in weights.items()}

def calculate_stock_price(team_name):
    """Kurs akcji = ważona kombinacja bieżących KPI (skala ~0..150)."""
    d = calculate_metrics_dict(team_name)
    if not d:
        return 100.0
    weights = get_stock_weights()
    price = sum(weights.get(mid, 0) * d.get(mid, 0) for mid in d)
    return round(price, 2)

def ensure_stock_seed(team_name):
    """Gwarantuje punkt startowy notowań (otwarcie sesji)."""
    team = state["teams"].get(team_name)
    if team is None:
        return
    ensure_team_fields(team)
    if not team["stock_history"]:
        team["stock_history"].append({
            "label": "OTWARCIE",
            "scenario": state.get("scenario_idx", 0),
            "round": 0,
            "price": calculate_stock_price(team_name)
        })

def record_stock_point(team_name):
    """Dopisuje nowy kurs po zatwierdzonej decyzji (rundzie)."""
    team = state["teams"].get(team_name)
    if team is None:
        return
    ensure_team_fields(team)
    ensure_stock_seed(team_name)
    s_idx = state.get("scenario_idx", 0)
    r_num = state.get("round", 0)
    team["stock_history"].append({
        "label": f"S{s_idx + 1}·R{r_num}",
        "scenario": s_idx,
        "round": r_num,
        "price": calculate_stock_price(team_name)
    })

def compute_badges():
    """System osiągnięć - porównuje wszystkie zespoły w sali i przyznaje tytuły.
    Zwraca: { team_name: [ (icon, title, desc), ... ] }"""
    teams = list(state["teams"].keys())
    badges = {t: [] for t in teams}
    if not teams:
        return badges

    role_map = get_role_map()
    liq, sec, rep = role_map["liquidity"], role_map["security"], role_map["reputation"]
    data = {t: calculate_metrics_dict(t) for t in teams}

    # 🏆 Stalowy Skarbiec - najwyższa płynność/budżet
    if liq:
        best = max(teams, key=lambda t: data[t].get(liq, 0))
        badges[best].append(("🏆", "Stalowy Skarbiec", "Najwyższy wynik KPI Budżet / Płynność w całej sali."))

    # 🛡️ Cyfrowa Forteca - najwyższy cyber/uptime
    if sec:
        best = max(teams, key=lambda t: data[t].get(sec, 0))
        badges[best].append(("🛡️", "Cyfrowa Forteca", "Najwyższy wynik KPI Cyber / Uptime w całej sali."))

    # 📢 Mistrzowie Iluzji - najwyższy PR/Zaufanie, ale bardzo niskie Bezpieczeństwo
    if rep and sec and len(teams) >= 1:
        avg_sec = sum(data[t].get(sec, 0) for t in teams) / len(teams)
        cand = max(teams, key=lambda t: data[t].get(rep, 0))
        if data[cand].get(sec, 0) < avg_sec:
            badges[cand].append(("📢", "Mistrzowie Iluzji", "Świetny PR / Zaufanie przy mocno zaniedbanym Bezpieczeństwie."))

    return badges

def get_round_pass_threshold(round_data):
    """Zwraca minimalny kurs akcji wymagany do przejścia rundy.
    Najpierw pass_condition rundy, potem global_pass_threshold z configu, w razie braku 0."""
    cfg = state.get("config") or {}
    global_thr = (cfg.get("global_pass_threshold") or {}).get("min_stock_price", 0)
    if round_data:
        return float((round_data.get("pass_condition") or {}).get("min_stock_price", global_thr))
    return float(global_thr)

def evaluate_round_and_advance():
    """v3.2: Ocena bieżącej rundy PRZED przejściem dalej.
      - zespoły poniżej progu (min_stock_price) zostają WYELIMINOWANE,
      - NOWE v3.2 (TWARDA ELIMINACJA): jeśli którykolwiek wskaźnik zespołu
        (calculate_metrics_dict) spadnie do 0 lub poniżej, zespół jest
        eliminowany BEZWZGLĘDNIE, niezależnie od kursu akcji,
      - zespoły, które przeszły, dostają bonus (bonus_on_pass) przez mechanizm God Mode,
      - następnie gra przechodzi do kolejnej rundy. Po OSTATNIEJ rundzie scenariusza
        silnik NIE startuje od razu kolejnego scenariusza, lecz wchodzi w stan
        PRZERWY (intermission) z round=0 i flagą state['intermission']=True.
    Zwraca podsumowanie: { "passed": [...], "eliminated": [...],
      "eliminated_details": [(team, reason), ...], "threshold": float }."""
    s_idx = state["scenario_idx"]
    r_num = state["round"]
    scen = state["scenarios"][s_idx]
    current_round = scen["rounds"].get(r_num) or scen["rounds"].get(str(r_num))

    summary = {"passed": [], "eliminated": [], "eliminated_details": [], "threshold": 0.0, "bonus": {}}

    # Ewaluacja tylko wtedy, gdy istnieje aktywna runda (round > 0)
    if current_round and r_num > 0:
        threshold = get_round_pass_threshold(current_round)
        bonus = current_round.get("bonus_on_pass", {}) or {}
        summary["threshold"] = threshold
        summary["bonus"] = bonus

        for t_name, t_data in state["teams"].items():
            ensure_team_fields(t_data)
            if t_data.get("is_eliminated"):
                continue  # już odpadł wcześniej

            metrics_now = calculate_metrics_dict(t_name)
            stock_price = calculate_stock_price(t_name)

            # WARUNEK 1 (TWARDY): którykolwiek wskaźnik wyzerowany (<= 0)
            zeroed = [mid for mid, val in metrics_now.items() if val <= 0]
            # WARUNEK 2: zbyt niski kurs akcji
            below_threshold = stock_price < threshold

            if zeroed or below_threshold:
                # Priorytet komunikatu: najpierw wskazujemy wyzerowane wskaźniki,
                # bo to bezwzględny powód eliminacji (np. "Budżet = 0").
                if zeroed:
                    reason = " + ".join(f"{get_metric_label(mid)} = 0" for mid in zeroed)
                else:
                    reason = f"kurs akcji {stock_price:.1f} < {threshold:.1f}"
                t_data["is_eliminated"] = True
                t_data["eliminated_in_round"] = r_num
                t_data["eliminated_in_scenario"] = s_idx
                t_data["eliminated_reason"] = reason
                summary["eliminated"].append(t_name)
                summary["eliminated_details"].append((t_name, reason))
            else:
                # Sukces -> bonus przez trwały mechanizm korekt (God Mode)
                if bonus:
                    adj = state.setdefault("manual_score_adjustments", {}).setdefault(t_name, {})
                    for metric_id, val in bonus.items():
                        if metric_id in get_metric_ids():
                            adj[metric_id] = adj.get(metric_id, 0) + int(val)
                summary["passed"].append(t_name)

    # Przejście do kolejnej fazy.
    # v3.2: po OSTATNIEJ rundzie scenariusza wchodzimy w PRZERWĘ (intermission)
    # zamiast natychmiast startować kolejny scenariusz.
    max_rounds = len(scen["rounds"])
    if state["round"] < max_rounds:
        state["round"] += 1
    else:
        if state["scenario_idx"] < len(state["scenarios"]) - 1:
            # Wskazujemy już kolejny scenariusz, ale czekamy na start przez Admina.
            state["scenario_idx"] += 1
            state["round"] = 0
            state["intermission"] = True
        else:
            state["status"] = "FINISHED"

    for t in state["teams"]:
        state["teams"][t]["ready"] = False

    state["round_start_time"] = time.time()
    state["last_round_summary"] = summary
    return summary

def render_live_leaderboard(highlight_team=None):
    """v3.1: Tablica wyników na żywo widoczna dla graczy (po złożeniu decyzji
    oraz po eliminacji). Sortowana po Kursie Akcji, a następnie po sumie punktów."""
    rows = []
    for t_name, t_data in state["teams"].items():
        ensure_team_fields(t_data)
        if t_data.get("is_eliminated"):
            status_txt = f"☠️ ELIMINACJA (R{t_data.get('eliminated_in_round', '?')})"
        elif t_data.get("ready"):
            status_txt = "✅ GOTOWY"
        else:
            status_txt = "⏳ MYŚLI"
        name = f"▶ {t_name}" if (highlight_team and t_name == highlight_team) else t_name
        rows.append({
            "ZESPÓŁ": name,
            "STATUS": status_txt,
            "KURS AKCJI": calculate_stock_price(t_name),
            "PUNKTY ŁĄCZNIE": sum(calculate_metrics(t_name)),
        })

    if rows:
        df = pd.DataFrame(rows).sort_values(
            by=["KURS AKCJI", "PUNKTY ŁĄCZNIE"], ascending=[False, False]
        ).reset_index(drop=True)
        df.insert(0, "MIEJSCE", [f"#{i+1}" for i in range(len(df))])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.caption("Brak danych do wyświetlenia.")

def render_kpi(label, value, color="var(--accent-cyan)"):
    pct = int((value / 150) * 100)
    current_color = "var(--accent-red)" if value < 45 else color
    st.markdown(f'<div class="kpi-header"><span>{label}</span><span>{pct}%</span></div><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%; background:{current_color}"></div></div><br>', unsafe_allow_html=True)

# --- WYKRES: STOCK TICKER (terminal giełdowy) ---
def render_stock_ticker(team_name):
    team = state["teams"].get(team_name)
    if team is None:
        return
    ensure_stock_seed(team_name)
    hist = team.get("stock_history", [])
    prices = [h["price"] for h in hist]
    labels = [h["label"] for h in hist]

    open_price = prices[0]
    last_price = prices[-1]
    prev_price = prices[-2] if len(prices) >= 2 else open_price
    delta = round(last_price - prev_price, 2)
    up = last_price >= open_price
    line_color = accent_green if up else accent_red
    arrow = "▲" if delta >= 0 else "▼"
    cls = "tk-up" if delta >= 0 else "tk-down"

    # Pasek nagłówkowy "terminala"
    st.markdown(
        f"<div class='ticker-bar'>"
        f"<span class='tk-sym'>📈 KURS AKCJI — {team_name}</span>"
        f"<span class='tk-price {cls}'>{last_price:.2f} <span style='font-size:0.9rem'>{arrow} {abs(delta):.2f}</span></span>"
        f"</div>",
        unsafe_allow_html=True
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=prices, mode="lines+markers",
        line=dict(color=line_color, width=2.5, shape="spline"),
        marker=dict(color=line_color, size=6),
        fill="tozeroy", fillcolor=hex_to_rgba(line_color.lstrip(), 0.12),
        hovertemplate="%{x}<br>Kurs: %{y:.2f}<extra></extra>"
    ))
    # Linia odniesienia (cena otwarcia)
    fig.add_hline(y=open_price, line_dash="dot", line_color=text_secondary, opacity=0.4)
    fig.update_layout(
        template="plotly_dark",
        height=210,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,15,29,0.6)",
        showlegend=False,
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title=None, gridcolor="rgba(148,163,184,0.12)"),
        font=dict(family="JetBrains Mono, monospace", size=11)
    )
    st.plotly_chart(fig, use_container_width=True, key=f"stock_chart_{team_name}",
                    config={"displayModeBar": False})

# --- WYKRES: RADAR (Debriefing 2.0) ---
def render_radar(team_name):
    cfg = state.get("config") or {}
    metrics_cfg = cfg.get("metrics", [])
    d = calculate_metrics_dict(team_name)
    labels = [m["label"] for m in metrics_cfg]
    values = [d.get(m["id"], 0) for m in metrics_cfg]
    if not labels:
        st.info("Brak danych metryk do wykresu radarowego.")
        return

    df = pd.DataFrame({"Metryka": labels, "Wynik": values})
    fig = px.line_polar(df, r="Wynik", theta="Metryka", line_close=True,
                        template="plotly_dark", range_r=[0, 150])
    fig.update_traces(fill="toself",
                      line_color=accent_primary,
                      fillcolor=hex_to_rgba(accent_primary, 0.25))
    fig.update_layout(
        height=360,
        margin=dict(l=40, r=40, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        polar=dict(bgcolor="rgba(10,15,29,0.6)",
                   radialaxis=dict(gridcolor="rgba(148,163,184,0.15)", angle=90),
                   angularaxis=dict(gridcolor="rgba(148,163,184,0.15)")),
        font=dict(family="Inter, sans-serif", size=12)
    )
    st.plotly_chart(fig, use_container_width=True, key=f"radar_{team_name}",
                    config={"displayModeBar": False})


# =====================================================================================
#  WIDOKI
# =====================================================================================

def login_view():
    render_header("LOGIN")
    if state["status"] == "NO_CONFIG":
        st.warning("SYSTEM ZABLOKOWANY: Oczekiwanie na konfigurację gry przez Administratora (Wgranie pliku YAML).")

    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>TERMINAL LOGIN</div>", unsafe_allow_html=True)
        t_id = st.text_input("IDENTYFIKATOR ZESPOŁU:").upper()
        if st.button("AUTORYZUJ DOSTĘP", use_container_width=True):
            if state["status"] == "NO_CONFIG":
                st.error("Nie można dołączyć. Gra nie została jeszcze skonfigurowana plikiem YAML.")
            elif t_id:
                if t_id not in state["teams"]:
                    state["teams"][t_id] = new_team_record()
                    ensure_stock_seed(t_id)
                st.session_state["team_name"] = t_id
                st.session_state["role"] = "team"
                # Synchronizacja punktu odniesienia dla powiadomień broadcast
                st.session_state["last_broadcast_id"] = state.get("broadcast_id", 0)
                st.rerun()
            else:
                st.warning("Wprowadź kryptonim pododdziału.")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔐 ROOT CONTROL (Panel Prowadzącego)"):
            if st.text_input("ROOT KEY:", type="password") == "admin":
                if st.button("ZALOGUJ DO DOWÓDZTWA"):
                    st.session_state["role"] = "admin"
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def admin_view():
    render_header("ROOT COMMAND CENTER")

    if state["status"] == "NO_CONFIG" or not state["scenarios"]:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>WGRAJ KONFIGURACJĘ SCENARIUSZY (YAML)</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Wybierz plik .yaml lub .yml", type=['yaml', 'yml'])
        if uploaded_file is not None:
            load_yaml_config(uploaded_file)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        s_name = state["scenarios"][state["scenario_idx"]]["name"]
        s_prefix = "NASTĘPNY SCENARIUSZ" if state.get("intermission") else "SCENARIUSZ"
        st.markdown(f"<div class='panel'>{s_prefix}: <b>{s_name}</b></div>", unsafe_allow_html=True)
    with c2:
        max_rounds = len(state["scenarios"][state["scenario_idx"]]["rounds"])
        if state.get("intermission"):
            st.markdown("<div class='panel'>RUNDA: <b>⏸️ PRZERWA</b></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='panel'>RUNDA: <b>{state['round']} / {max_rounds}</b></div>", unsafe_allow_html=True)
    with c3:
        if st.button("🔄 SYNCHRONIZUJ STATUSY ZESPOŁÓW", use_container_width=True):
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎮 STEROWANIE RUNDĄ",
        "📊 MONITOR ZESPOŁÓW",
        "🛰️ KOMUNIKATY (BREAKING NEWS)",
        "📜 HISTORIA I EKSPORT"
    ])

    # --- TAB 1: STEROWANIE RUNDĄ ---
    with tab1:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>STEROWANIE FAZAMI OPERACYJNYMI</div>", unsafe_allow_html=True)

        if state.get("intermission"):
            # === v3.2: PRZERWA MIĘDZY SCENARIUSZAMI ===
            next_name = state["scenarios"][state["scenario_idx"]]["name"]
            st.markdown(
                f"<div class='scenario-header' style='border-left-color:var(--accent-yellow)'>"
                f"<h3 style='margin:0; color:var(--accent-yellow)'>⏸️ PRZERWA MIĘDZY SCENARIUSZAMI</h3>"
                f"<p style='margin:6px 0 0'>Zakończono poprzedni etap. Gracze widzą teraz pełnoekranowy ranking "
                f"podsumowujący i oczekują na Twój sygnał. Następny scenariusz: <b>{next_name}</b>.</p></div>",
                unsafe_allow_html=True
            )

            # Podsumowanie ostatnio ocenionej rundy (z precyzyjnym powodem eliminacji)
            last = state.get("last_round_summary")
            if last:
                if last.get("passed"):
                    st.success(f"✅ Przeszły poprzednią rundę: {', '.join(last['passed'])}")
                if last.get("eliminated_details"):
                    elim_txt = ", ".join(f"{n} ({r})" for n, r in last["eliminated_details"])
                    st.error(f"☠️ Wyeliminowani: {elim_txt}")

            st.caption("💡 Wskazówka: w zakładce MONITOR ZESPOŁÓW możesz teraz wskrzesić wyeliminowane zespoły "
                       "(God Mode) — najpierw podbij im wyzerowany wskaźnik powyżej 0, potem kliknij „Wskrześ”.")

            if st.button(f"▶ ROZPOCZNIJ SCENARIUSZ: {next_name}", use_container_width=True, key="start_next_scenario"):
                state["intermission"] = False
                state["round"] = 1
                state["round_start_time"] = time.time()
                for t in state["teams"]:
                    state["teams"][t]["ready"] = False
                st.success(f"Uruchomiono scenariusz: {next_name}")
                time.sleep(1.0)
                st.rerun()
        else:
            # === NORMALNE STEROWANIE RUNDĄ ===
            # Podgląd progu przetrwania bieżącej rundy
            cur_s = state["scenario_idx"]
            cur_r = state["round"]
            cur_round = state["scenarios"][cur_s]["rounds"].get(cur_r) or state["scenarios"][cur_s]["rounds"].get(str(cur_r))
            if cur_round and cur_r > 0:
                thr = get_round_pass_threshold(cur_round)
                bonus = cur_round.get("bonus_on_pass", {}) or {}
                bonus_txt = ", ".join(f"{get_metric_label(k)}: +{v}" for k, v in bonus.items()) or "brak"
                st.markdown(
                    f"<div class='god-readout'>PRÓG PRZETRWANIA TEJ RUNDY: kurs akcji ≥ <b>{thr:.1f}</b> "
                    f"&nbsp;|&nbsp; TWARDA ELIMINACJA: dowolny wskaźnik = 0 "
                    f"&nbsp;|&nbsp; BONUS ZA PRZEJŚCIE: {bonus_txt}</div>",
                    unsafe_allow_html=True
                )

            if st.button("⏩ ZAKOŃCZ RUNDĘ, ROZDAJ BONUSY I AKTYWUJ NASTĘPNY ETAP", use_container_width=True):
                summary = evaluate_round_and_advance()
                if summary["passed"]:
                    st.success(f"✅ Przeszły rundę (bonus przyznany): {', '.join(summary['passed'])}")
                if summary["eliminated_details"]:
                    elim_txt = ", ".join(f"{n} ({r})" for n, r in summary["eliminated_details"])
                    st.error(f"☠️ Wyeliminowani: {elim_txt}")
                if state.get("intermission"):
                    st.info("⏸️ Scenariusz zakończony — gra wchodzi w PRZERWĘ. Użyj przycisku startu kolejnego etapu.")
                time.sleep(1.2)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 2: MONITOR ZESPOŁÓW + GOD MODE ---
    with tab2:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>RANKING I WSKAŹNIKI NA ŻYWO</div>", unsafe_allow_html=True)
        monitor_data = []
        metrics_cfg = state["config"]["metrics"]
        for t, d in state["teams"].items():
            m = calculate_metrics(t)
            if d.get("is_eliminated"):
                status_txt = f"☠️ ELIMINACJA (R{d.get('eliminated_in_round', '?')})"
            else:
                status_txt = "✅ GOTOWY" if d.get("ready") else "⏳ MYŚLI"
            row = {"ZESPÓŁ": t, "STATUS": status_txt, "PUNKTY": sum(m), "KURS AKCJI": calculate_stock_price(t)}
            for idx, item in enumerate(metrics_cfg):
                row[item["label"]] = m[idx]
            monitor_data.append(row)
        if monitor_data:
            st.dataframe(pd.DataFrame(monitor_data).sort_values("PUNKTY", ascending=False), hide_index=True, use_container_width=True)
        else:
            st.info("Brak zalogowanych zespołów.")
        st.markdown("</div>", unsafe_allow_html=True)

        # --- GOD MODE: RĘCZNA KOREKTA METRYK ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='danger-zone'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label' style='color:var(--accent-yellow)'>⚡ GOD MODE — RĘCZNA KOREKTA METRYK (NAGRODA / KARA)</div>", unsafe_allow_html=True)

        if not state["teams"]:
            st.info("Brak zalogowanych zespołów. Korekta będzie możliwa, gdy dołączy co najmniej jeden zespół.")
        else:
            metric_labels = [item["label"] for item in metrics_cfg]
            label_to_id = {item["label"]: item["id"] for item in metrics_cfg}

            gc1, gc2, gc3 = st.columns([1.2, 1.2, 0.8])
            with gc1:
                sel_team = st.selectbox("ZESPÓŁ", list(state["teams"].keys()), key="god_team")
            with gc2:
                sel_metric_label = st.selectbox("METRYKA", metric_labels, key="god_metric")
            with gc3:
                delta = st.number_input("ZMIANA (+/-)", min_value=-150, max_value=150, value=10, step=5, key="god_delta")

            if st.button("💉 ZASTOSUJ KOREKTĘ", use_container_width=True, key="god_apply"):
                if not state["config"] or not state["scenarios"]:
                    st.error("Nie można zastosować korekty: brak wgranej konfiguracji (YAML).")
                elif sel_team not in state["teams"]:
                    st.error("Wybrany zespół nie istnieje (mógł zostać zresetowany).")
                else:
                    metric_id = label_to_id[sel_metric_label]
                    adj = state.setdefault("manual_score_adjustments", {}).setdefault(sel_team, {})
                    adj[metric_id] = adj.get(metric_id, 0) + int(delta)
                    sign = "+" if delta >= 0 else ""
                    st.success(f"Zastosowano korektę {sign}{int(delta)} do '{sel_metric_label}' dla zespołu {sel_team}. Paski KPI gracza zaktualizują się automatycznie.")
                    st.rerun()

            # Podgląd aktywnych korekt
            active_adj = state.get("manual_score_adjustments", {})
            readout_rows = []
            for tname, mvals in active_adj.items():
                for mid, dv in mvals.items():
                    if dv != 0:
                        lbl = next((it["label"] for it in metrics_cfg if it["id"] == mid), mid)
                        readout_rows.append({"ZESPÓŁ": tname, "METRYKA": lbl, "SKUMULOWANA KOREKTA": f"{'+' if dv >= 0 else ''}{dv}"})
            if readout_rows:
                st.markdown("<div class='panel-label' style='margin-top:12px'>AKTYWNE KOREKTY</div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(readout_rows), hide_index=True, use_container_width=True)

            # --- v3.2: WSKRZESZENIE WYELIMINOWANEGO ZESPOŁU (REVIVE) ---
            sel_team_data = state["teams"].get(sel_team)
            if sel_team_data and ensure_team_fields(sel_team_data).get("is_eliminated"):
                st.markdown("<br>", unsafe_allow_html=True)
                reason = sel_team_data.get("eliminated_reason") or "—"
                elim_r = sel_team_data.get("eliminated_in_round", "?")
                st.markdown(
                    f"<div class='god-readout' style='color:var(--accent-red)'>"
                    f"☠️ ZESPÓŁ {sel_team} WYELIMINOWANY (runda {elim_r}, powód: {reason}).</div>",
                    unsafe_allow_html=True
                )

                # Wskazujemy aktualnie wyzerowane wskaźniki, by Admin wiedział, co podbić.
                metrics_now = calculate_metrics_dict(sel_team)
                zeroed_now = [get_metric_label(mid) for mid, v in metrics_now.items() if v <= 0]
                if zeroed_now:
                    st.warning(
                        f"⚠️ Wskaźniki na zerze: {', '.join(zeroed_now)}. Najpierw użyj powyższej korekty "
                        f"God Mode (+), aby podbić je powyżej 0, a dopiero potem wskrześ zespół — inaczej "
                        f"odpadnie ponownie w kolejnej ewaluacji."
                    )
                else:
                    st.info("✅ Wszystkie wskaźniki tego zespołu są powyżej 0 — można bezpiecznie wskrzesić.")

                if st.button("🚑 COFNIJ ELIMINACJĘ (WSKRZEŚ ZESPÓŁ)", use_container_width=True, key="revive_team"):
                    sel_team_data["is_eliminated"] = False
                    sel_team_data["eliminated_in_round"] = None
                    sel_team_data["eliminated_in_scenario"] = None
                    sel_team_data["eliminated_reason"] = None
                    st.success(f"🚑 Zespół {sel_team} został przywrócony do aktywnej gry! Widok gracza odblokuje się automatycznie.")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 3: BREAKING NEWS / BROADCAST + CELOWANE WRZUTKI (v3) ---
    with tab3:
        metrics_cfg = state["config"]["metrics"]
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>CELOWANA WRZUTKA / KOMUNIKAT ALARMOWY (TARGETED INJECT)</div>", unsafe_allow_html=True)

        team_names = list(state["teams"].keys())
        recipient_options = ["📢 WSZYSTKIE ZESPOŁY"] + [f"🎯 {t}" for t in team_names]

        with st.form("broadcast_form", clear_on_submit=True):
            recipient = st.selectbox("ODBIORCA:", recipient_options, key="bc_recipient")
            msg = st.text_area(
                "Treść komunikatu Dowództwa:",
                placeholder="np. Kontrola UODO weszła do waszego biura! / Media opublikowały artykuł o wycieku danych!",
                height=100
            )

            st.markdown("<div class='panel-label' style='color:var(--accent-yellow); margin-top:8px'>⚡ DOŁĄCZ KARĘ / NAGRODĘ (GOD MODE — opcjonalnie)</div>", unsafe_allow_html=True)
            st.caption("Ustaw suwak różny od 0, aby wraz z komunikatem nałożyć korektę wskaźnika na odbiorcę.")
            slider_vals = {}
            scols = st.columns(min(len(metrics_cfg), 4) or 1)
            for i, item in enumerate(metrics_cfg):
                with scols[i % len(scols)]:
                    slider_vals[item["id"]] = st.slider(
                        item["label"], min_value=-50, max_value=50, value=0, step=5,
                        key=f"bc_slider_{item['id']}"
                    )

            sent = st.form_submit_button("📡 WYŚLIJ WRZUTKĘ DO ODBIORCY", use_container_width=True)
            if sent:
                target = "ALL"
                if recipient.startswith("🎯"):
                    target = recipient.replace("🎯 ", "", 1)
                adjustments = {mid: v for mid, v in slider_vals.items() if v != 0}
                if push_broadcast(msg, target=target, adjustments=adjustments):
                    where = "wszystkich zespołów" if target == "ALL" else f"zespołu {target}"
                    extra = " + nałożono korektę God Mode" if adjustments else ""
                    st.success(f"Wrzutka nadana do {where}{extra}. Pojawi się jako Toast + czerwony pasek tylko u odbiorcy.")
                else:
                    st.warning("Treść komunikatu nie może być pusta.")
        st.markdown("</div>", unsafe_allow_html=True)

        # Aktualny komunikat + historia nadań
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>AKTUALNIE NADAWANY KOMUNIKAT</div>", unsafe_allow_html=True)
        if state.get("broadcast_msg"):
            tgt = state.get("broadcast_target", "ALL")
            tgt_lbl = "WSZYSTKIE ZESPOŁY" if tgt == "ALL" else f"ODBIORCA: {tgt}"
            st.markdown(f"<div class='broadcast-bar'><span class='bc-label'>// KOMUNIKAT DOWÓDZTWA — {tgt_lbl}</span><span class='bc-text'>{state['broadcast_msg']}</span></div>", unsafe_allow_html=True)
            if st.button("🧹 WYCZYŚĆ PASEK KOMUNIKATÓW", key="clear_broadcast"):
                if state.get("broadcast_msg"):
                    state.setdefault("broadcast_history", []).append({
                        "id": state.get("broadcast_id", 0),
                        "time": datetime.datetime.now().strftime("%H:%M:%S"),
                        "text": state["broadcast_msg"],
                        "target": state.get("broadcast_target", "ALL")
                    })
                state["broadcast_msg"] = ""
                state["broadcast_target"] = "ALL"
                state["broadcast_id"] = state.get("broadcast_id", 0) + 1
                st.rerun()
        else:
            st.info("Brak aktywnego komunikatu.")

        history = list(reversed(state.get("broadcast_history", [])))
        if history:
            st.markdown("<div class='panel-label' style='margin-top:12px'>ARCHIWUM NADAŃ</div>", unsafe_allow_html=True)
            st.dataframe(
                pd.DataFrame([{"CZAS": h["time"], "ODBIORCA": h.get("target", "ALL"), "TREŚĆ": h["text"]} for h in history]),
                hide_index=True, use_container_width=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 4: HISTORIA I EKSPORT ---
    with tab4:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-label'>PEŁNY AUDYT DECYZJI</div>", unsafe_allow_html=True)
        full_history = []
        for t_name, t_data in state["teams"].items():
            for s_idx_str, r_decs in t_data.get("decisions", {}).items():
                s_id = int(s_idx_str)
                scen_name = state["scenarios"][s_id]["name"]
                for r_num_str, roles in r_decs.items():
                    r_num = int(r_num_str)
                    rd = state["scenarios"][s_id]["rounds"].get(r_num) or state["scenarios"][s_id]["rounds"].get(str(r_num))
                    if not rd:
                        continue
                    for role, choice in roles.items():
                        full_history.append({
                            "SCENARIUSZ": scen_name, "RUNDA": r_num, "ZESPÓŁ": t_name,
                            "SEKCJA": rd["questions"][role]["label"], "DECYZJA": choice
                        })
        if full_history:
            df_hist = pd.DataFrame(full_history)
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            st.download_button("📥 EKSPORTUJ LOGI DO CSV", data=df_hist.to_csv(index=False).encode('utf-8-sig'), file_name="audit_report.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("Brak historii decyzji.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("⚠️ RESET GRY"):
        st.markdown("<div class='danger-zone'>", unsafe_allow_html=True)
        if st.button("☢️ BEZPOWROTNE CZYSZCZENIE SILNIKA"):
            state.update({
                "config": None, "scenarios": [], "scenario_idx": 0, "round": 0,
                "teams": {}, "status": "NO_CONFIG", "round_start_time": None,
                "intermission": False, "last_round_summary": None,
                "broadcast_msg": "", "broadcast_id": 0, "broadcast_target": "ALL",
                "broadcast_history": [], "manual_score_adjustments": {}
            })
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# --- FRAGMENT: SYNCHRONIZACJA FAZY GRY (status / scenariusz / runda) ---
@st.fragment(run_every=2)
def phase_sync_fragment(team_name):
    """Wykrywa zmianę fazy gry zarządzaną przez Dowództwo (Admina).

    WAŻNE (naprawa białego ekranu / wylogowania po 'AKTYWUJ NASTĘPNY ETAP'):
    Przy ZWYKŁYM awansie rundy / scenariusza NIE wymuszamy już pełnego rerunu
    aplikacji. Pełny rerun przeładowywał całą stronę u wszystkich graczy naraz
    (biały ekran), a przy wielu sesjach potrafił zerwać sesję i wyrzucać do
    ekranu logowania. Treść nowej rundy i tak aktualizuje się "w miejscu", bo
    panele gracza (center/left/broadcast) działają na st.fragment(run_every=2)
    i czytają bieżący stan przy każdym cyklu.

    Pełny rerun robimy WYŁĄCZNIE, gdy faktycznie trzeba przerysować layout całej
    strony, czyli przy:
      - zakończeniu gry (FINISHED) -> wejście na ekran DEBRIEFING 2.0,
      - twardym resecie silnika (NO_CONFIG) -> powrót do logowania."""
    status = state.get("status")
    sig = (status, state.get("scenario_idx"), state.get("round"))
    last = st.session_state.get("_phase_sig")
    if last is None:
        st.session_state["_phase_sig"] = sig
        return
    if sig != last:
        st.session_state["_phase_sig"] = sig
        # Tylko zmiana wymagająca przebudowy całego layoutu wymusza pełny rerun.
        if status in ("FINISHED", "NO_CONFIG"):
            st.rerun()
        # W przeciwnym razie: nic nie robimy — panele run_every same pokażą nową rundę.


# --- FRAGMENT: PASEK KOMUNIKATÓW DOWÓDZTWA (auto-poll, obsługa celowanych wrzutek) ---
@st.fragment(run_every=2)
def broadcast_bar_fragment(team_name):
    current_id = state.get("broadcast_id", 0)
    current_msg = state.get("broadcast_msg", "")
    target = state.get("broadcast_target", "ALL")

    # Czy komunikat jest skierowany do TEGO zespołu?
    visible = (target == "ALL") or (target == team_name)

    # Wykrycie NOWEGO komunikatu -> st.toast() tylko u właściwego odbiorcy
    last_seen = st.session_state.get("last_broadcast_id", 0)
    if current_id != last_seen:
        st.session_state["last_broadcast_id"] = current_id
        if current_msg and visible:
            st.toast(f"📡 NOWY KOMUNIKAT DOWÓDZTWA: {current_msg}", icon="🚨")

    # Pasek komunikatów (czerwony) nad środkowym panelem - tylko dla odbiorcy
    if current_msg and visible:
        label = "PRIORYTET ALARMOWY" if target == "ALL" else f"WIADOMOŚĆ CELOWANA → {team_name}"
        st.markdown(
            f"<div class='broadcast-bar'><span class='bc-label'>// KOMUNIKAT DOWÓDZTWA — {label}</span>"
            f"<span class='bc-text'>{current_msg}</span></div>",
            unsafe_allow_html=True
        )


# --- FRAGMENT: LEWA KOLUMNA (KPI + Archiwum Decyzji), auto-poll dla korekt God Mode ---
@st.fragment(run_every=2)
def left_panel_fragment(team_name):
    if team_name not in state["teams"]:
        return
    team_data = state["teams"][team_name]
    m = calculate_metrics(team_name)
    metrics_cfg = state["config"]["metrics"]

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("<span class='panel-label'>WYNIKI OPERACYJNE</span>", unsafe_allow_html=True)
    for idx, item in enumerate(metrics_cfg):
        render_kpi(item["label"], m[idx], item["color"])
    st.markdown("</div>", unsafe_allow_html=True)

    # --- ARCHIWUM DECYZJI (bieżący scenariusz) ---
    st.markdown("<br>", unsafe_allow_html=True)
    s_idx = state["scenario_idx"]
    scen = state["scenarios"][s_idx]
    rounds_cfg = scen.get("rounds", {})
    my_decisions = team_data.get("decisions", {}).get(str(s_idx), {})

    with st.expander("🗄️ ARCHIWUM DECYZJI", expanded=False):
        if not my_decisions:
            st.caption("Brak zapisanych decyzji w tym scenariuszu.")
        else:
            # Sortuj rundy rosnąco
            for r_num_str in sorted(my_decisions.keys(), key=lambda x: int(x)):
                r_num = int(r_num_str)
                rd = rounds_cfg.get(r_num) or rounds_cfg.get(str(r_num))
                round_title = rd.get("title", f"RUNDA {r_num}") if rd else f"RUNDA {r_num}"
                st.markdown(f"<div class='panel-label' style='margin-top:6px'>RUNDA {r_num} — {round_title}</div>", unsafe_allow_html=True)
                for role, choice in my_decisions[r_num_str].items():
                    section_label = role
                    if rd:
                        section_label = rd.get("questions", {}).get(role, {}).get("label", role)
                    st.markdown(
                        f"<div class='archive-item'><span class='ai-meta'>{section_label}</span><br>"
                        f"<span class='ai-choice'>{choice}</span></div>",
                        unsafe_allow_html=True
                    )

    if st.button("ODŚWIEŻ TERMINAL 🔄", use_container_width=True, key="refresh_left"):
        # Pełny rerun na żądanie gracza: przerysowuje też zegar (nowa runda) i layout.
        st.rerun()


# --- FRAGMENT: ŚRODKOWY PANEL (Giełda + OSINT + formularz decyzji), auto-poll ---
@st.fragment(run_every=2)
def center_panel_fragment(team_name):
    if team_name not in state["teams"]:
        return
    team_data = ensure_team_fields(state["teams"][team_name])

    if state["status"] == "FINISHED":
        st.success("SYMULACJA ZAKOŃCZONA. OCZEKUJ NA DEBRIEFING Z TRENEREM.")
        return

    # === v3.2: PRZERWA MIĘDZY SCENARIUSZAMI (INTERMISSION LEADERBOARD) ===
    # Pełnoekranowy ranking na żywo zamiast formularza decyzji — zarówno dla
    # zespołów aktywnych, jak i wyeliminowanych. Czekamy na start kolejnego
    # etapu przez Admina (bez wymuszania pełnego rerunu — fragment poll co 2s).
    if state.get("intermission"):
        next_name = state["scenarios"][state["scenario_idx"]]["name"]
        st.markdown(
            "<div class='scenario-header' style='border-left-color:var(--accent-yellow)'>"
            "<h1 style='margin:0; color:var(--accent-yellow); font-size:1.8rem'>ZAKOŃCZONO SCENARIUSZ – PODSUMOWANIE ETAPU</h1>"
            f"<p style='margin:10px 0 0; color:var(--text-secondary)'>Oczekiwanie na rozpoczęcie kolejnego etapu "
            f"przez Dowództwo: <b style='color:var(--text-primary)'>{next_name}</b></p></div>",
            unsafe_allow_html=True
        )
        st.markdown("<div class='panel'><span class='panel-label'>🏟️ RANKING NA ŻYWO — PODSUMOWANIE ETAPU</span>", unsafe_allow_html=True)
        render_live_leaderboard(highlight_team=team_name)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # === v3.1: EKRAN ELIMINACJI (zespół nie spełnił warunku przejścia rundy) ===
    if team_data.get("is_eliminated"):
        elim_r = team_data.get("eliminated_in_round", "?")
        reason = team_data.get("eliminated_reason")
        reason_txt = f" Powód: {reason}." if reason else " Zbyt niski kurs akcji / wskaźniki krytyczne."
        st.error(f"☠️ ZESPÓŁ WYELIMINOWANY W RUNDZIE {elim_r}.{reason_txt}")
        st.markdown("<div class='panel'><span class='panel-label'>🏟️ RANKING ZESPOŁÓW (TABLICA WYNIKÓW)</span>", unsafe_allow_html=True)
        render_live_leaderboard(highlight_team=team_name)
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Możesz dalej śledzić zmagania pozostałych zespołów. Wynik końcowy zobaczysz w Debriefingu.")
        return

    if state["round"] == 0:
        st.info("STREFA BEZPIECZNA: Oczekiwanie na uruchomienie fazy operacyjnej przez Dowództwo.")
        return

    # === FILAR FINANSOWY: GIEŁDA / KURS AKCJI (nad formularzem decyzji) ===
    render_stock_ticker(team_name)
    st.markdown("<br>", unsafe_allow_html=True)

    if team_data["ready"]:
        st.warning("TRANSMISJA ZABEZPIECZONA. Oczekiwanie na pozostałe zespoły / Dowództwo. Podgląd sytuacji w sali:")
        st.markdown("<div class='panel'><span class='panel-label'>🏟️ RANKING NA ŻYWO (TABLICA WYNIKÓW)</span>", unsafe_allow_html=True)
        render_live_leaderboard(highlight_team=team_name)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    s_idx = state["scenario_idx"]
    r_num = state["round"]
    rd = state["scenarios"][s_idx]["rounds"].get(r_num) or state["scenarios"][s_idx]["rounds"].get(str(r_num))

    st.markdown(f"<div class='scenario-header'><h2>{rd['title']}</h2><p>{rd['desc']}</p></div>", unsafe_allow_html=True)
    st.caption("🔄 Jeśli zegar po prawej nie wskazuje nowej rundy, użyj przycisku „ODŚWIEŻ TERMINAL” w lewym panelu.")

    # === FILAR CYBER: SKLEP Z RAPORTAMI WYWIADOWCZYMI (OSINT) ===
    osint_hint = rd.get("osint_hint")
    if osint_hint:
        gconf = get_gamification_cfg()
        cost = int(gconf.get("osint_cost", 10))
        role_map = get_role_map()
        cost_metric = gconf.get("osint_cost_metric") or role_map.get("liquidity") or (get_metric_ids()[0] if get_metric_ids() else None)
        cost_metric_label = get_metric_label(cost_metric) if cost_metric else "BUDŻET"

        purchase_key = f"{s_idx}_{r_num}"
        already_bought = purchase_key in team_data.get("osint_purchased", [])

        if already_bought:
            st.markdown(
                f"<div class='osint-box'><span class='ob-label'>🛰️ RAPORT WYWIADOWCZY (OSINT) — ODSZYFROWANY</span>"
                f"<span class='ob-text'>{osint_hint}</span></div>",
                unsafe_allow_html=True
            )
        else:
            if st.button(f"🛒 KUP RAPORT WYWIADOWCZY (Koszt: -{cost} {cost_metric_label})",
                         use_container_width=True, key=f"osint_buy_{s_idx}_{r_num}"):
                if cost_metric:
                    adj = state.setdefault("manual_score_adjustments", {}).setdefault(team_name, {})
                    adj[cost_metric] = adj.get(cost_metric, 0) - cost
                team_data.setdefault("osint_purchased", []).append(purchase_key)
                st.toast(f"🛰️ Zakupiono raport OSINT. Pobrano -{cost} z: {cost_metric_label}", icon="🛒")
                st.rerun(scope="fragment")

    with st.form("team_decision"):
        choices = {}
        for role, q in rd["questions"].items():
            st.write(f"**{q['label']}**")
            choices[role] = st.radio("Strategia:", list(q["options"].keys()), key=f"{role}_{s_idx}_{r_num}", label_visibility="collapsed")
        if st.form_submit_button("AUTORYZUJ I WYŚLIJ TRANSMISJĘ"):
            if str(s_idx) not in team_data["decisions"]:
                team_data["decisions"][str(s_idx)] = {}
            team_data["decisions"][str(s_idx)][str(r_num)] = choices
            team_data["ready"] = True
            # FILAR FINANSOWY: nowy kurs akcji trafia na wykres po zatwierdzeniu decyzji
            record_stock_point(team_name)
            st.rerun(scope="fragment")


# --- DEBRIEFING 2.0: RADAR + ODZNAKI (ekran końca gry dla zespołu) ---
def debrief_view(team_name):
    render_header(f"{team_name} // DEBRIEFING 2.0")

    badges_all = compute_badges()
    my_badges = badges_all.get(team_name, [])
    final_metrics = calculate_metrics_dict(team_name)
    total = sum(final_metrics.values())
    final_price = calculate_stock_price(team_name)

    elim = state["teams"].get(team_name, {}).get("is_eliminated")
    elim_r = state["teams"].get(team_name, {}).get("eliminated_in_round")
    status_line = (
        f"<span style='color:var(--accent-red); font-weight:700'>☠️ ZESPÓŁ WYELIMINOWANY W RUNDZIE {elim_r}</span>"
        if elim else
        "<span style='color:var(--accent-green); font-weight:700'>✅ ZESPÓŁ PRZETRWAŁ DO KOŃCA SYMULACJI</span>"
    )

    st.markdown(
        f"<div class='debrief-hero'><h2 style='margin:0'>🏁 RAPORT KOŃCOWY — {team_name}</h2>"
        f"<p style='margin:6px 0 0'>{status_line}</p>"
        f"<p style='color:var(--text-secondary); margin:6px 0 0'>Symulacja zakończona. Poniżej analiza kształtu strategii, "
        f"finalny kurs akcji oraz przyznane tytuły na tle całej sali.</p></div>",
        unsafe_allow_html=True
    )

    # Pas z kluczowymi liczbami
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f"<div class='panel'><span class='panel-label'>SUMA PUNKTÓW</span><div style='font-size:1.8rem;font-weight:800;color:var(--accent-cyan)'>{total}</div></div>", unsafe_allow_html=True)
    with k2:
        st.markdown(f"<div class='panel'><span class='panel-label'>FINALNY KURS AKCJI</span><div style='font-size:1.8rem;font-weight:800;color:var(--accent-green)'>{final_price:.2f}</div></div>", unsafe_allow_html=True)
    with k3:
        st.markdown(f"<div class='panel'><span class='panel-label'>ZDOBYTE TYTUŁY</span><div style='font-size:1.8rem;font-weight:800;color:var(--accent-yellow)'>{len(my_badges)}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<span class='panel-label'>📡 RADAR STRATEGII (KSZTAŁT KOŃCOWY)</span>", unsafe_allow_html=True)
        render_radar(team_name)
        st.markdown("</div>", unsafe_allow_html=True)

        # Historia notowań akcji
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<span class='panel-label'>📈 PRZEBIEG NOTOWAŃ AKCJI</span>", unsafe_allow_html=True)
        render_stock_ticker(team_name)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<span class='panel-label'>🎖️ SYSTEM OSIĄGNIĘĆ — TWOJE TYTUŁY</span>", unsafe_allow_html=True)
        if my_badges:
            for icon, title, desc in my_badges:
                st.markdown(
                    f"<div class='badge-card'><span class='bd-icon'>{icon}</span> "
                    f"<span class='bd-title'>{title}</span>"
                    f"<div class='bd-desc'>{desc}</div></div>",
                    unsafe_allow_html=True
                )
        else:
            st.caption("Ten zespół nie zdobył tytułu wyróżnienia w tej rozgrywce. Liczy się udział i wnioski!")
        st.markdown("</div>", unsafe_allow_html=True)

        # Tablica tytułów całej sali
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<span class='panel-label'>🏟️ TYTUŁY W CAŁEJ SALI</span>", unsafe_allow_html=True)
        room_rows = []
        for t, blist in badges_all.items():
            if blist:
                room_rows.append({"ZESPÓŁ": t, "TYTUŁY": "  ".join(f"{ic} {ti}" for ic, ti, _ in blist)})
        if room_rows:
            st.dataframe(pd.DataFrame(room_rows), hide_index=True, use_container_width=True)
        else:
            st.caption("Brak przyznanych tytułów.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- KOŃCOWA TABLICA WYNIKÓW CAŁEJ SALI ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("<span class='panel-label'>🏟️ KOŃCOWY RANKING ZESPOŁÓW</span>", unsafe_allow_html=True)
    render_live_leaderboard(highlight_team=team_name)
    st.markdown("</div>", unsafe_allow_html=True)


def team_view():
    team_name = st.session_state.get("team_name")

    # 1) Twardy reset silnika (brak konfiguracji) -> czysty powrót do logowania.
    if state.get("status") == "NO_CONFIG" or not state.get("config"):
        st.session_state["role"] = None
        st.session_state.pop("team_name", None)
        st.rerun()
        return

    # 2) Sesja nie zna tożsamości zespołu -> ekran logowania.
    if not team_name:
        st.session_state["role"] = None
        st.rerun()
        return

    # 3) Sesja zna zespół, ale nie ma go w stanie globalnym (np. po reconnect /
    #    restarcie hostingu, gdy gra nadal trwa) -> AUTOMATYCZNA re-rejestracja,
    #    zamiast wyrzucania gracza do ekranu "dodaj zespół". Dzięki temu uczestnik
    #    nie wypada z gry po zmianie etapu.
    if team_name not in state["teams"]:
        state["teams"][team_name] = new_team_record()
        ensure_stock_seed(team_name)

    team_data = ensure_team_fields(state["teams"][team_name])

    # WATCHER FAZY GRY: pełny rerun tylko przy końcu gry / resecie (patrz docstring).
    # Zwykły awans rundy aktualizuje treść w miejscu, bez przeładowania strony.
    phase_sync_fragment(team_name)

    # --- DEBRIEFING 2.0: pełnoekranowy ekran końca gry ---
    if state["status"] == "FINISHED":
        debrief_view(team_name)
        return

    render_header(team_name)

    # PASEK KOMUNIKATÓW DOWÓDZTWA (nad środkowym panelem scenariusza) + toast
    broadcast_bar_fragment(team_name)

    l, c, r = st.columns([1, 2.2, 0.9])

    with l:
        # KPI + Archiwum Decyzji (fragment auto-aktualizuje korekty God Mode)
        left_panel_fragment(team_name)

    with c:
        # Giełda + OSINT + formularz decyzji (fragment - submit nie przeładowuje timera)
        center_panel_fragment(team_name)

    with r:
        st.markdown(
            f"<div class='panel'><span class='panel-label'>ŁĄCZNOŚĆ</span>"
            f"<div style='text-align:center; font-size:2rem;'>{'🟢' if team_data['ready'] else '🟡'}</div></div>",
            unsafe_allow_html=True
        )

        # --- ZEGAR PRESJI CZASU ---
        # OPTYMALIZACJA: komponent renderuje się TYLKO w głównym ciele skryptu.
        # Interakcje gracza dzieją się wewnątrz st.fragment (powyżej), więc nie
        # wywołują pełnego rerun -> iframe z zegarem NIE jest przeładowywany i nie mruga.
        # Odliczanie liczone jest po stronie JS od bezwzględnego znacznika czasu.
        time_limit = state["config"].get("time_limit_sec", 180)
        start_time = state.get("round_start_time")

        if time_limit > 0 and start_time and not team_data["ready"] and state["round"] > 0:
            end_time_ms = int((start_time + time_limit) * 1000)

            components.html(f"""
                <style>
                    body {{
                        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                        background-color: {panel_bg};
                        color: {text_primary};
                        text-align: center;
                        margin: 0;
                        padding: 15px;
                        border-radius: 6px;
                        border: 1px solid #334155;
                        border-left: 4px solid #ef4444;
                    }}
                    .label {{
                        color: #ef4444;
                        font-size: 11px;
                        font-weight: 700;
                        letter-spacing: 1px;
                        margin-bottom: 5px;
                        display: block;
                        text-transform: uppercase;
                    }}
                    .time {{ font-family: monospace; font-size: 32px; font-weight: 900; }}
                    .expired {{ color: #ef4444; font-size: 16px; font-weight: 700; line-height: 35px; }}
                </style>
                <div>
                    <span class="label">Czas do decyzji</span>
                    <div id="countdown" class="time">--:--</div>
                </div>
                <script>
                    var endTime = {end_time_ms};
                    function tick() {{
                        var now = new Date().getTime();
                        var distance = endTime - now;
                        if (distance < 0) {{
                            clearInterval(timerInterval);
                            document.getElementById("countdown").innerHTML = "<span class='expired'>CZAS MINĄŁ</span>";
                        }} else {{
                            var m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                            var s = Math.floor((distance % (1000 * 60)) / 1000);
                            document.getElementById("countdown").innerHTML = m + ":" + (s < 10 ? "0" : "") + s;
                        }}
                    }}
                    tick();
                    var timerInterval = setInterval(tick, 1000);
                </script>
            """, height=120)


# =====================================================================================
#  ROUTER
# =====================================================================================
if "role" not in st.session_state or st.session_state["role"] is None:
    login_view()
elif st.session_state["role"] == "admin":
    admin_view()
else:
    team_view()
