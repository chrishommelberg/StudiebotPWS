import re
import time
import html
import datetime
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Studiebot", page_icon="🧭", layout="centered")

def geheim(naam):
    """Leest een geheime instelling (zoals de API-key) uit .streamlit/secrets.toml
    (op je eigen computer) of uit de Secrets van Streamlit Community Cloud (online)."""
    try:
        return st.secrets[naam]
    except Exception:
        return None


API_KEY = geheim("GEMINI_API_KEY")
if not API_KEY:
    st.error('Geen API-key gevonden. Zet GEMINI_API_KEY = "jouw-key" in het bestand '
             '.streamlit/secrets.toml (op je eigen computer) of bij Secrets (online).')
    st.stop()

client = genai.Client(api_key=API_KEY)

MODELLEN = ["gemini-3.1-flash-lite", "gemini-3.6-flash"]
ZOEK_TOOL = types.Tool(google_search=types.GoogleSearch())

def _bronnen_uit(response):
    """Haalt de websites op die Gemini bij het zoeken heeft gebruikt."""
    bronnen, gezien = [], set()
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
        for c in chunks:
            if c.web and c.web.uri and c.web.uri not in gezien:
                gezien.add(c.web.uri)
                bronnen.append({"titel": c.web.title or c.web.domain or "bron", "url": c.web.uri})
    except Exception:
        pass
    return bronnen[:5]

def _probeer(prompt, zoeken):
    """Probeert de modellen na elkaar, met wachttijd bij overbelasting."""
    laatste_fout = None
    config = types.GenerateContentConfig(tools=[ZOEK_TOOL]) if zoeken else None
    for model in MODELLEN:
        for poging in range(4):
            try:
                response = client.models.generate_content(model=model, contents=prompt, config=config)
                if response.text:
                    return response
                laatste_fout = RuntimeError("Leeg antwoord van de AI")
                break
            except Exception as e:
                laatste_fout = e
                tekst = str(e)
                if "503" in tekst or "429" in tekst or "UNAVAILABLE" in tekst:
                    time.sleep(2 * (poging + 1))
                else:
                    break
    raise laatste_fout

def vraag_gemini(prompt, zoeken=False, veilige_prompt=None):
    """Geeft (tekst, bronnen, live, zoekfout).
    Met zoeken=True gebruikt de AI Google Zoeken. Het antwoord telt alleen als 'live' als er
    echt bronnen bij zitten. Lukt dat niet, dan wordt veilige_prompt (zonder datums) zonder
    zoeken gebruikt, zodat de AI geen datums kan verzinnen."""
    zoekfout = ""
    if zoeken:
        try:
            response = _probeer(prompt, True)
            bronnen = _bronnen_uit(response)
            if bronnen:
                return response.text, bronnen, True, ""
            zoekfout = "De AI vond geen bronnen via Google Zoeken."
        except Exception as e:
            zoekfout = str(e)
    response = _probeer(veilige_prompt or prompt, False)
    return response.text, [], False, zoekfout

# "slaat_op" bewaart het antwoord apart, zodat we het in de AI-opdracht kunnen gebruiken.
# "alleen_bij_diploma" laat een vraag alleen zien bij bepaalde diploma's.
vragen = [
    {"type": "keuze", "tekst": "Op welk niveau zit je nu op school?",
     "opties": ["Mavo", "Havo", "Vwo", "Anders"], "slaat_op": "diploma"},
    {"type": "keuze", "tekst": "Welk profiel heb je (of kies je)?",
     "opties": ["Cultuur & Maatschappij (C&M)", "Economie & Maatschappij (E&M)",
                "Natuur & Techniek (N&T)", "Natuur & Gezondheid (N&G)", "Anders"],
     "slaat_op": "profiel", "alleen_bij_diploma": ["Havo", "Vwo"]},
    {"type": "multi", "tekst": "Welk soort opleiding wil je overwegen?",
     "opties": ["MBO", "HBO", "WO"], "slaat_op": "niveaus",
     "hulp": "Je kunt er meerdere kiezen. De adviezen blijven binnen jouw keuze."},
    {"type": "open", "tekst": "Wat zou je doen op een dag zonder verplichtingen of schoolwerk?"},
    {"type": "keuze", "tekst": "Als je in een team werkt, welke rol pak je het snelst?",
     "opties": ["De aanjager die knopen doorhakt", "De denker die het overzicht bewaakt", "De verbinder die zorgt dat iedereen meedoet"]},
    {"type": "open", "tekst": "Noem een probleem (groot of klein) dat je onlangs hebt opgelost, en hoe je dat aanpakte."},
    {"type": "keuze", "tekst": "Welke uitspraak past het best bij jou?",
     "opties": ["Ik wil snel resultaat zien", "Ik wil tot op de bodem begrijpen hoe iets werkt", "Ik wil vooral dat mensen zich beter voelen door wat ik doe"]},
    {"type": "open", "tekst": "Welk vak of onderwerp op school vond je het minst leuk, en waarom?"},
    {"type": "keuze", "tekst": "Hoe ga je om met een taak die je niet meteen begrijpt?",
     "opties": ["Ik zoek het zelf helemaal uit voor ik het opgeef", "Ik vraag snel hulp aan iemand anders", "Ik laat het even liggen en kom er later op terug"]},
    {"type": "open", "tekst": "Is er een vaardigheid die je nu al goed beheerst, waar je zelf best trots op bent?"},
    {"type": "keuze", "tekst": "Wat spreekt je meer aan in een toekomstige baan?",
     "opties": ["Veel afwisseling en onzekerheid", "Duidelijke structuur en herhaling", "Een mix van beide"]},
]

# ---------- Stijl ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Work+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"]  { font-family: 'Work Sans', sans-serif; }
.block-container { max-width: 780px; padding-top: 2rem; }

.hero-panel {
    background: linear-gradient(135deg, #16324F 0%, #1F4463 100%);
    border-radius: 16px; padding: 2.2rem 2.4rem; margin-bottom: 2.2rem;
}
.hero-panel .icon { font-size: 2rem; }
.hero-panel h1 { font-family: 'Fraunces', serif; font-weight: 700; font-size: 2.1rem; color: #FFFFFF; margin: 0.4rem 0 0.5rem 0; }
.hero-panel p { color: #C9D6DE; margin: 0; font-size: 0.97rem; }

.step-item { display:flex; align-items:flex-start; gap:0.7rem; position:relative; padding-bottom:1.4rem; }
.step-item:last-child { padding-bottom:0; }
.step-item:last-child .step-line { display:none; }
.step-dot { width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:0.72rem; font-weight:600; flex-shrink:0; z-index:1; }
.step-item.done .step-dot { background:#16324F; color:#fff; }
.step-item.active .step-dot { background:#D9A441; color:#16324F; box-shadow:0 0 0 4px rgba(217,164,65,0.25); }
.step-item.todo .step-dot { background:#fff; border:2px solid #C7CFC9; color:#8B968F; }
.step-line { position:absolute; left:12px; top:26px; bottom:-14px; width:2px; background:#C7CFC9; }
.step-item.done .step-line, .step-item.active .step-line { background:#16324F; }
.step-label-text { font-size:0.83rem; padding-top:3px; color:#33403A; }
.step-item.todo .step-label-text { color:#9AA39D; }

.question-card { background: #FFFFFF; border-left: 4px solid #D9A441; border-radius: 8px; padding: 1.6rem 1.8rem; margin-bottom: 1.3rem; }
.question-card h3 { font-family: 'Fraunces', serif; font-weight: 600; color: #16324F; font-size: 1.25rem; margin: 0; }

.advies-intro { background: #FFFFFF; border-radius: 10px; padding: 1.6rem 2rem; margin-bottom: 1.4rem; box-shadow: 0 1px 3px rgba(22,50,79,0.08); }
.advies-intro h3 { font-family: 'Fraunces', serif; color: #16324F; margin-top: 0; font-size: 1.5rem; }
.advies-intro p { color:#2E3A34; margin: 0.4rem 0; }

.studie-card { background: #FFFFFF; border-radius: 10px; padding: 1.5rem 1.8rem; margin-bottom: 1.1rem; box-shadow: 0 1px 3px rgba(22,50,79,0.08); }
.studie-card h4 { font-family: 'Fraunces', serif; color: #16324F; margin: 0 0 0.5rem 0; font-size: 1.25rem; }
.studie-card p { color:#2E3A34; margin: 0.3rem 0; }
.studie-card ul { margin: 0.3rem 0 0.6rem 0; padding-left: 1.2rem; }

.info-box { background: #F3F7F5; border-left: 4px solid #3D7A72; border-radius: 6px; padding: 1.1rem 1.4rem; margin-top: 0.8rem; }
.info-box p { color:#28362F; margin: 0.35rem 0; }
.subkop { margin-top: 0.9rem !important; color:#16324F !important; }
.match-rij { display:flex; align-items:center; gap:0.8rem; margin: 0.2rem 0 0.8rem 0; }
.match-score { font-family: 'Fraunces', serif; font-weight:700; color:#16324F; font-size:1.05rem; white-space:nowrap; }
.match-balk { flex:1; height:9px; background:#E4E9E2; border-radius:6px; overflow:hidden; }
.match-vulling { height:100%; background: linear-gradient(90deg, #D9A441, #E8BC63); border-radius:6px; }
.bronnen { font-size:0.82rem; margin-top:0.6rem; color:#55645B; }
.bronnen a { color:#16324F; }
.live-label { font-size:0.8rem; color:#55645B; margin-bottom:0.4rem; }
.feedback-card { background: #FFF8E8; border-left: 4px solid #D9A441; border-radius: 8px; padding: 1.3rem 1.6rem; margin: 1.6rem 0 0.8rem 0; }
.feedback-card h4 { font-family: 'Fraunces', serif; color: #16324F; margin: 0 0 0.4rem 0; font-size: 1.15rem; }
.feedback-card p { color:#3A473F; margin: 0.2rem 0; font-size: 0.93rem; }

div.stButton > button { background-color: #16324F; color: #FFFFFF; border: none; border-radius: 6px; padding: 0.5rem 1.5rem; font-weight: 500; }
div.stButton > button:hover { background-color: #0F233A; color: #FFFFFF; }
</style>
""", unsafe_allow_html=True)

# ---------- Status ----------
if "stap" not in st.session_state:
    st.session_state.stap = -1  # -1 = welkomstscherm
    st.session_state.antwoorden = []
    st.session_state.advies = None
    st.session_state.extra_info = {}  # naam studie -> tekst met extra info
    st.session_state.diploma = None   # Mavo / Havo / Vwo / Anders
    st.session_state.profiel = None   # alleen ingevuld bij Havo/Vwo
    st.session_state.niveaus = []     # gekozen opleidingsniveaus (MBO / HBO / WO)


def actieve_vragen():
    """Geeft de vragen die voor deze leerling gelden (profielvraag alleen bij havo/vwo)."""
    uit = []
    for v in vragen:
        voorwaarde = v.get("alleen_bij_diploma")
        if voorwaarde and st.session_state.diploma is not None \
                and st.session_state.diploma not in voorwaarde:
            continue
        uit.append(v)
    return uit


def niveau_tekst():
    """Zet de gekozen niveaus om naar leesbare tekst, bijv. 'MBO en HBO'."""
    n = st.session_state.niveaus or ["MBO", "HBO", "WO"]
    if len(n) == 1:
        return n[0]
    return ", ".join(n[:-1]) + " en " + n[-1]


def achtergrond_tekst():
    """Huidig niveau en eventueel profiel, bijv. 'Havo, profiel Natuur & Techniek (N&T)'."""
    tekst = st.session_state.diploma or "onbekend niveau"
    if st.session_state.profiel:
        tekst += f", profiel {st.session_state.profiel}"
    return tekst


def sla_antwoord_op(vraag, tekst, ruwe_waarde):
    """Bewaart het antwoord en gaat naar de volgende vraag."""
    st.session_state.antwoorden.append({"vraag": vraag["tekst"], "antwoord": tekst})
    if vraag.get("slaat_op"):
        st.session_state[vraag["slaat_op"]] = ruwe_waarde
    st.session_state.stap += 1
    st.rerun()


def markdown_naar_html(tekst):
    """Zet simpele markdown (###, **, lijstjes) om naar nette HTML."""
    t = re.sub(r'^#{2,4}\s*(.+)$', r'<p class="subkop"><strong>\1</strong></p>', tekst, flags=re.MULTILINE)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    regels, uit, in_lijst = t.split("\n"), [], False
    for regel in regels:
        r = regel.strip()
        if r.startswith("* ") or r.startswith("- "):
            if not in_lijst:
                uit.append("<ul>"); in_lijst = True
            uit.append(f"<li>{r[2:]}</li>")
        else:
            if in_lijst:
                uit.append("</ul>"); in_lijst = False
            if r:
                uit.append(r if r.startswith("<p") else f"<p>{r}</p>")
    if in_lijst:
        uit.append("</ul>")
    return "\n".join(uit)


def split_advies_in_studies(tekst):
    """Splitst het AI-antwoord op de '### Studienaam'-koppen in losse blokken."""
    delen = re.split(r'^#{2,3}\s*(.+)$', tekst, flags=re.MULTILINE)
    intro = delen[0].strip()
    studies = []
    for i in range(1, len(delen), 2):
        naam = delen[i].strip()
        inhoud = delen[i + 1].strip() if i + 1 < len(delen) else ""
        studies.append({"naam": naam, "inhoud": inhoud})
    return intro, studies


actief = actieve_vragen()

# ---------- Hero ----------
st.markdown("""
<div class="hero-panel">
    <span class="icon">🧭</span>
    <h1>Studiebot</h1>
    <p>Beantwoord een aantal vragen en krijg een persoonlijk, zelfstandig opgesteld studieadvies.</p>
</div>
""", unsafe_allow_html=True)

# ---------- Welkomstscherm ----------
if st.session_state.stap == -1:
    st.markdown("""
    <div class="question-card">
        <h3>Welkom!</h3>
        <p style="margin-top:0.6rem; color:#3A473F;">
            Je krijgt zo ongeveer 10 vragen: eerst over je huidige opleiding en wat je wilt gaan doen,
            daarna over hoe je denkt, werkt en wat je drijft.
            Aan het eind denkt de AI vrij na over welke opleidingen het beste passen.
        </p>
        <p style="margin-top:0.6rem; color:#6B7B74; font-size:0.85rem;">
            Je antwoorden worden alleen gebruikt om je advies te maken en worden niet door Studiebot
            opgeslagen. Voor het advies worden ze wel naar Google (Gemini) gestuurd.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Optionele toegangscode: alleen actief als TOEGANGSCODE in de Secrets staat.
    code_nodig = geheim("TOEGANGSCODE")
    ingevoerd = st.text_input("Toegangscode", type="password") if code_nodig else None

    if st.button("Begin"):
        if code_nodig and ingevoerd != str(code_nodig):
            st.warning("Deze toegangscode klopt niet.")
        else:
            st.session_state.stap = 0
            st.rerun()

# ---------- Vragen ----------
elif st.session_state.stap < len(actief):
    col_stepper, col_vraag = st.columns([1, 2.6])

    with col_stepper:
        html = ""
        for i, v in enumerate(actief):
            status = "done" if i < st.session_state.stap else ("active" if i == st.session_state.stap else "todo")
            teken = "✓" if status == "done" else str(i + 1)
            html += f"""
            <div class="step-item {status}">
                <div class="step-dot">{teken}</div>
                <div class="step-line"></div>
                <div class="step-label-text">Vraag {i + 1}</div>
            </div>
            """
        st.markdown(html, unsafe_allow_html=True)

    with col_vraag:
        vraag = actief[st.session_state.stap]
        widget_key = f"vraag_{vraag['tekst']}"
        st.markdown(f'<div class="question-card"><h3>{vraag["tekst"]}</h3></div>', unsafe_allow_html=True)

        if vraag["type"] == "multi":
            keuze = st.pills("Kies één of meer opties:", vraag["opties"], selection_mode="multi",
                             key=widget_key, label_visibility="collapsed")
            if vraag.get("hulp"):
                st.caption(vraag["hulp"])
            if st.button("Volgende"):
                if keuze:
                    sla_antwoord_op(vraag, ", ".join(keuze), list(keuze))
                else:
                    st.warning("Kies minstens één optie.")

        elif vraag["type"] == "keuze":
            keuze = st.radio("Kies een optie:", vraag["opties"], key=widget_key, label_visibility="collapsed")
            if st.button("Volgende"):
                sla_antwoord_op(vraag, keuze, keuze)

        else:
            antwoord = st.text_area("Jouw antwoord:", key=widget_key, label_visibility="collapsed")
            if st.button("Volgende"):
                if antwoord.strip():
                    sla_antwoord_op(vraag, antwoord, antwoord)
                else:
                    st.warning("Vul eerst een antwoord in.")

# ---------- AI-aanroep voor het advies ----------
elif st.session_state.advies is None:
    with st.spinner("De AI denkt na over jouw studieadvies..."):
        overzicht = "\n".join(f"- {a['vraag']} → {a['antwoord']}" for a in st.session_state.antwoorden)

        prompt = f"""Een leerling heeft de volgende vragen beantwoord met het oog op een studiekeuze:

{overzicht}

Denk volledig zelfstandig na over welke vervolgopleidingen (in Nederland) het beste
aansluiten bij deze specifieke antwoorden. Gebruik GEEN vooraf vastgestelde lijst van
opleidingen — bedenk zelf de meest logische en best onderbouwde opties.

BELANGRIJK 1: de leerling wil uitsluitend opleidingen op het niveau {niveau_tekst()} overwegen.
Beveel dus NOOIT een opleiding aan op een ander niveau, ook niet als die theoretisch beter
zou passen. Bij MBO gaat het om opleidingen op MBO-niveau 2, 3 of 4 (noem het niveau erbij).

BELANGRIJK 2: de leerling zit nu op: {achtergrond_tekst()}. Houd rekening met toelaatbaarheid.
Als een gekozen niveau niet rechtstreeks bereikbaar is vanuit dit diploma (bijvoorbeeld WO
vanaf mavo), beveel dan toch opleidingen op het gekozen niveau aan, maar benoem kort welke
route daarvoor nodig is (zoals eerst MBO-4 of havo).

Geef een top 3, gesorteerd van beste naar minste match. Houd je EXACT aan dit formaat per opleiding:

### Naam van de opleiding
Match: X/10
- eerste reden, met een concrete verwijzing naar een specifiek antwoord van de leerling
- tweede reden, idem
- derde reden, idem
Let op: (alleen invullen als er een belangrijk aandachtspunt is, zoals een tussenstap of een
mogelijk nadeel; laat deze regel anders weg)

De score X is een geheel getal van 1 tot 10 en moet eerlijk verschillen tussen de opleidingen:
geef niet alles een 9. Schrijf voor de eerste koptekst geen inleiding."""

        try:
            st.session_state.advies = vraag_gemini(prompt)[0]
        except Exception as e:
            st.session_state.advies = (
                "Er ging iets mis bij het ophalen van het advies. Dit is vaak tijdelijk "
                "(Google's servers overbelast) — probeer over een minuutje opnieuw te beginnen.\n\n"
                f"Technische foutmelding: {e}"
            )
    st.rerun()

# ---------- Advies + extra info per studie ----------
else:
    intro, studies = split_advies_in_studies(st.session_state.advies)

    st.markdown(f'<div class="advies-intro"><h3>Jouw studieadvies</h3>'
                f'<p>Huidig niveau: <strong>{achtergrond_tekst()}</strong><br>'
                f'Gekozen opleidingsniveau: <strong>{niveau_tekst()}</strong></p>'
                f'{markdown_naar_html(intro) if intro else ""}</div>',
                unsafe_allow_html=True)

    for i, studie in enumerate(studies):
        inhoud = studie['inhoud']
        score = None
        m = re.search(r'^\s*\**\s*Match:?\s*\**\s*(\d{1,2})\s*(?:/\s*10)?\s*\**\s*$', inhoud, flags=re.MULTILINE | re.IGNORECASE)
        if m:
            score = max(1, min(10, int(m.group(1))))
            inhoud = (inhoud[:m.start()] + inhoud[m.end():]).strip()
        match_html = ""
        if score:
            match_html = (f'<div class="match-rij"><span class="match-score">Match {score}/10</span>'
                          f'<div class="match-balk"><div class="match-vulling" style="width:{score*10}%"></div></div></div>')
        st.markdown(f"""
        <div class="studie-card">
            <h4>{html.escape(studie['naam'])}</h4>
            {match_html}
            {markdown_naar_html(inhoud)}
        </div>
        """, unsafe_allow_html=True)

        if st.button(f"Meer info over {studie['naam']}", key=f"info_btn_{i}"):
            with st.spinner("Praktische info opzoeken..."):
                vandaag = datetime.date.today().strftime("%d-%m-%Y")
                basis = f"""voor de opleiding "{studie['naam']}" in Nederland, voor een scholier die uitsluitend
opleidingen op niveau {niveau_tekst()} overweegt (ga dus alleen in op dit niveau).
De leerling zit nu op: {achtergrond_tekst()}."""
                punten_1_2 = f"""1. In welke Nederlandse steden deze opleiding op dit niveau wordt aangeboden
   (bij MBO: bij welke ROC's).
2. Hoe toegankelijk de opleiding is (bijvoorbeeld vrije instroom, decentrale selectie,
   numerus fixus) en de toelatingseisen (vooropleiding, vakken). Ga specifiek in op wat dit
   betekent voor een leerling met {achtergrond_tekst()}: is directe toelating mogelijk, of is
   een tussenstap nodig?"""
                info_prompt = f"""Vandaag is het {vandaag}. Zoek via Google actuele, betrouwbare informatie op {basis}
Gebruik bij voorkeur officiële bronnen (websites van hogescholen, universiteiten, ROC's,
Studiekeuze123, DUO).

Geef kort en praktisch:
{punten_1_2}
3. De eerstvolgende open dagen. Noem een open dag ALLEEN met instelling en datum als je die
   zelf op een officiële site hebt gevonden. Verzin of raad nooit een datum en schrijf nooit
   dat je een website hebt geraadpleegd als dat niet zo is. Vind je ze niet, zeg dat dan
   en noem alleen de gebruikelijke periode.

Sluit af met één korte zin dat de leerling toelatingseisen en data altijd moet checken op de
officiële website van de instelling."""
                veilige_prompt = f"""Geef beknopte, praktische informatie {basis}
Je kunt NIET op internet zoeken; antwoord alleen uit je eigen kennis.

{punten_1_2}
3. In welke periode van het jaar open dagen voor dit soort opleiding doorgaans plaatsvinden
   (bijvoorbeeld: najaar en voorjaar). Noem GEEN exacte data, GEEN instellingen met datums,
   en schrijf nooit dat je een website hebt geraadpleegd of dat gegevens actueel zijn.

Sluit af met één korte zin dat exacte toelatingseisen en open-dagdata per instelling en per
jaar verschillen, en dat de leerling dit altijd moet checken op de officiële website."""
                try:
                    tekst, bronnen, live, zoekfout = vraag_gemini(info_prompt, zoeken=True, veilige_prompt=veilige_prompt)
                    st.session_state.extra_info[studie['naam']] = {"tekst": tekst, "bronnen": bronnen, "live": live, "zoekfout": zoekfout}
                except Exception as e:
                    st.session_state.extra_info[studie['naam']] = {
                        "tekst": ("Kon deze info nu niet ophalen (server overbelast). Probeer het zo nog eens.\n\n"
                                  f"Technische foutmelding: {e}"),
                        "bronnen": [], "live": False, "zoekfout": ""}

        if studie['naam'] in st.session_state.extra_info:
            info = st.session_state.extra_info[studie['naam']]
            if info["live"]:
                label = "🔎 Live opgezocht via Google"
            else:
                label = ("⚠️ Niet live gecontroleerd: dit komt uit de kennis van de AI en kan verouderd zijn. "
                         "Open dagen zijn daarom niet getoond; check de website van de instelling.")
                if info.get("zoekfout"):
                    label += f" (Zoeken mislukte: {html.escape(info['zoekfout'][:160])})"
            bron_html = ""
            if info["bronnen"]:
                links = " · ".join(f'<a href="{html.escape(b["url"])}" target="_blank">{html.escape(b["titel"])}</a>'
                                   for b in info["bronnen"])
                bron_html = f'<p class="bronnen">Bronnen: {links}</p>'
            st.markdown(f'<div class="info-box"><p class="live-label">{label}</p>'
                        f'{markdown_naar_html(info["tekst"])}{bron_html}</div>', unsafe_allow_html=True)

    formulier_url = geheim("FORMULIER_URL")
    if formulier_url:
        st.markdown('<div class="feedback-card"><h4>Help mijn onderzoek</h4><p>Past dit advies bij je? Beantwoord een paar korte vragen (ongeveer 2 minuten). Het formulier is anoniem en bevat jouw antwoorden op de vragen niet.</p></div>', unsafe_allow_html=True)
        st.link_button("Geef je mening", formulier_url, type="primary")

    st.write("")
    if st.button("Opnieuw beginnen"):
        st.session_state.stap = -1
        st.session_state.antwoorden = []
        st.session_state.advies = None
        st.session_state.extra_info = {}
        st.session_state.diploma = None
        st.session_state.profiel = None
        st.session_state.niveaus = []
        st.rerun()

