# Nakijkestafette

Een demo van **AI-nakijken als estafette**: kleine, gespecialiseerde modellen
geven het nakijken van een exit-ticket aan elkaar door, elk met één taak. Het
ticket gaat over de waterkringloop, met 20 synthetische leerlingantwoorden.
Een live dashboard laat tijdens de run zien wie aan het woord is, en markeert
de antwoorden waar het systeem twijfelt: die kijkt de docent zelf na.

| Stap | Taak | Model | Soort |
|------|------|-------|-------|
| 0 | Voorfilter: leeg of geen letters = ongeldig | vaste regel | geen model |
| 1 | Triage: is dit een serieuze poging? | Tev1 (`ERASMUS.tev1:4b`, terugval `tev1:0.8b`) | beslismodel |
| 2 | Score 0–2 + fout-tag + zekerheid | Clef 27B via LiteLLM System One (terugval: Nimble 9B) | beslismodel |
| 3 | 1–2 zinnen feedback per leerling | Qwen3.8 | taalmodel |
| 4 | Briefing en actieplan voor de docent | Qwen3.8 | taalmodel |

**Ontwerpprincipe:** laat beslismodellen kiezen en taalmodellen schrijven.
Beslismodellen voeren geen gesprek: ze krijgen een situatie en vaste opties,
en geven een keuze terug, met kansen. Daardoor zijn ze snel en zeggen ze erbij
hoe zeker ze zijn. Een score met minder dan 60% kans op de gekozen optie wordt
als twijfelgeval gemarkeerd.

## Installeren

Python 3.10 of nieuwer. Er zijn geen extra packages nodig (alleen de
standaardbibliotheek).

```bash
cp .env.example .env     # en vul NOLAI_API_KEY en LITELLM_API_KEY in
```

`.env` mag in deze map of in de map erboven staan, en gaat nooit mee de
repository in.

## Gebruik

```bash
python pipeline.py                  # volledige run: 20 leerlingen
python pipeline.py --limiet 4       # snelle smoke-test
python pipeline.py --simulatie      # laatste echte run naspelen, zonder gateway
python pipeline.py --geen-browser   # dashboard niet automatisch openen
```

`dashboard.html` opent vanzelf en beweegt mee: het leest `live_state.js` elke
seconde opnieuw in. De simulatie speelt `simulatie_data.json` na, de opname van
de laatste volledige, geslaagde run. Handig om te oefenen, of als de gateway
hapert tijdens een demo.

Elke leerling heeft een vooraf vastgelegde verwachte uitkomst (`verwacht` in
`pipeline.py`). De modellen krijgen die nooit te zien; het dashboard toont waar
ze ervan afwijken. Pas die verwachtingen gerust aan naar je eigen oordeel.

### Vergelijken met alleen Qwen

```bash
python vergelijk_qwen.py
```

Doet hetzelfde werk (triage, score, feedback) met alleen Qwen3.8, in een paar
varianten, en meet tijd en juiste scores. Uitvoer in de terminal en in
`resultaten/vergelijk_qwen.json`.

## Wat er in de map staat

| Bestand | Wat |
|---------|-----|
| `pipeline.py` | De estafette: leerlingen, prompts, de vier stappen, het rapport |
| `live_dashboard.py` | Voorfilter, gateway- en System One-client, live state, simulatie |
| `dashboard.html` | Het live dashboard (ook het sjabloon voor de momentopnames) |
| `vergelijk_qwen.py` | De vergelijking met alleen Qwen3.8 |
| `simulatie_data.json` | Opname van de laatste geslaagde run, voor `--simulatie` |
| `resultaten/` | Momentopnames (`resultaat_<datum-tijd>.html`), het Markdown-rapport en de vergelijking |
| `.env.example` | Sjabloon voor de API-sleutels |

De momentopnames in `resultaten/` zijn losse HTML-bestanden: het dashboard met
de uitkomst van die run erin, om te bewaren of door te sturen. De vroege
momentopnames laten de ontwikkeling zien, van de eerste versie met alleen
chat-aanroepen tot de huidige met Clef via System One.

## Technische keuzes

* **Transport.** Tev1, Nimble en Qwen gaan via de Ollama-route van de
  NOLAI-gateway (`/ollama/api/chat`) met `think: false`. Via de
  OpenAI-compatibele route laat het denken zich niet uitzetten, en dan kost één
  keuze 30 tot 130 seconden in plaats van ongeveer een seconde.
* **Clef via System One.** Clef draait via LiteLLM (`/v1/systemone`): score,
  fout-tag en de kansen per optie in één aanroep.
* **Zekerheid.** De twijfelgrens gebruikt de kans op de gekozen optie. Het veld
  `confidence` in het System One-antwoord is géén kans: het zegt hoe
  geconcentreerd de kansen zijn.
* **Twee triagevragen.** Een antwoord gaat pas apart als Tev1 het geen serieuze
  poging vindt én het als onzin aanmerkt. Zo houden ook leerlingen met een
  misconceptie een score en feedback.
* **Robuust.** Terugval per stap, retries bij tijdelijke fouten, en sleutels
  worden uit foutmeldingen gefilterd.

## Bekende beperkingen

* `tev1:4b` geeft op dit moment een 404; de triage valt dan terug op `tev1:0.8b`.
* Nimble staat niet in LiteLLM en wordt daarom alleen als terugval via de chat-route gebruikt.
* Een run duurt ongeveer 2 tot 2,5 minuut per klas, waarvan het meeste in de
  feedback en de briefing van Qwen zit.
* De onderbouwing is dun: 20 synthetische antwoorden en een handvol runs. Dit
  laat een ontwerpprincipe zien, geen bewijs.
* De kwaliteit van de feedback aan leerling en docent is niet systematisch
  geëvalueerd.
