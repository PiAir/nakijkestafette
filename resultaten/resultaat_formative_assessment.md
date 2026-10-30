# Formative Assessment Pipeline — Resultaat

_Genereerd op 2026-10-30 12:52 · endpoint `https://chat.nolai.nl/ollama/api/chat` · estafette: Tev1 → Clef → Qwen3.8 → Qwen3.8_

## De opgave

> Leg in maximaal 3 zinnen uit hoe de waterkringloop werkt. Noem minimaal drie fasen.

20 synthetische leerlingantwoorden (exit-ticket) zijn door de pijplijn gelopen: triage, foutenscoring, gepersonaliseerde feedback en een docent-briefing.

## De estafette (welk model deed wat)

| Stap | Rol | Model | Substituent gebruikt? | Duur |
|------|-----|-------|-----------------------|------|
| Triage | Triage: is dit een serieuze poging? | `ERASMUS.tev1:0.8b` | ja | 3s |
| Scoring | Score 0–2 + fout-tag met zekerheid (System One) | `clef:27b` | nee | 22s |
| Feedback | Formatieve feedback (taalmodel) | `CLUSTER.qwen3.8:latest` | nee | 54s |
| Briefing | Docent-briefing + actieplan | `CLUSTER.qwen3.8:latest` | nee | 48s |

## Stap 1 — Triage (Tev1)

| Leerling | Antwoord (uitsnede) | Classificatie |
|----------|---------------------|---------------|
| L01 | Water verdampt door de warmte van de zon, kondenseert in de hoge lucht | GELDIG |
| L02 | De waterkringloop bestaat uit verdamping, condensatie en neerslag. Wat | GELDIG |
| L03 | Het water gaat omhoog als damp, maakt wolken en dan regent het weer. | GELDIG |
| L04 | Water verdamp en dan regent het weer op de grond. | GELDIG |
| L05 | Eerst valt er neerslag uit de lucht en daarna verdampt het water weer | GELDIG |
| L06 | De zon verwarmt het water in de zee en dat komt omhoog als wolken in d | GELDIG |
| L07 | Wolken vallen uit de lucht en dan stroomt het water in de zee. | GELDIG |
| L08 | Het water stroomt via rivieren naar de zee en komt dan weer terug in d | GELDIG |
| L09 | Als het warm is dan verdampt het water en dat wordt dan wind die de wo | GELDIG |
| L10 | De waterkringloop is een soort kring van water die altijd door blijft | GELDIG |
| L11 | Ik denk dat het te maken heeft met de maan, want het water gaat omhoog | GELDIG |
| L12 | Omdat vissen het water in de lucht duwen met hun staarten. | GELDIG |
| L13 | De waterkringloop bestaat omdat het water honger heeft naar de aarde. | GELDIG |
| L14 | Waternoom is een dier dat in de zee woont en dat spuilt dan het water | GELDIG |
| L15 | Omdat de zon 's nachts het water drinkt en 's ochtends weer brukt op d | GELDIG |
| L16 | 1234567890 | ONGELDIG |
| L17 | (leeg) | ONGELDIG |
| L18 | In de zee wordt water verdampt en dan regent het weer op de bergen. | GELDIG |
| L19 | Het water loopt langzaam de berg op en dan valt het er weer van af als | GELDIG |
| L20 | Iets met wolken en regen, maar ik weet de fases niet echt te benoemen. | GELDIG |

## Stap 2 — Scoring & Stap 3 — Feedback (Clef + Qwen3.8)

| Leerling | Score | Fout-tag | Feedback |
|----------|-------|----------|----------|
| L01 | 2/2 | [Geen fout] | Mooi gedaan, je beschrijft de volledige waterkringloop perfect. Je hebt alle drie de belangrijke fasen, namelijk verdamping, condensatie en neerslag, correct aan elkaar gekoppeld. |
| L02 | 2/2 | [Geen fout] | Mooi gedaan, je beschrijft de drie fasen van de waterkringloop precies en in de juiste volgorde. Je hebt de stof volledig onder de knie en bent klaar voor de volgende stap. |
| L03 | 2/2 | [Geen fout] | Prima, je beschrijft de volledige waterkringloop exact in de juiste volgorde. Je hebt de stof volledig onder de knie. |
| L04 | 1/2 | [Vergeet condensatie] | Goed dat je de verdamping en neerslag benoemt, maar vergeet niet dat waterdamp eerst moet condenseren tot wolkjes voordat het kan regenen. Probeer de volledige cyclus te benoemen: verdamping, condensatie en neerslag. |
| L05 | 1/2 | [Vergeet condensatie] | Je hebt goed begrepen dat neerslag en verdamping deel uitmaken van de kringloop, maar je bent de stap condensatie vergeten. Probeer de volgorde te corrigeren door te bedenken dat het water eerst moet condenseren tot wolkjes voordat het als neerslag naar beneden kan vallen. |
| L06 | 1/2 | [Vergeet neerslag] | Goed gedaan dat je de verdamping en condensatie correct beschrijft, maar vergeet niet dat het water na de wolken als neerslag weer naar beneden valt. Kijk even goed naar de volledige kringloop: verdamping, condensatie en neerslag. |
| L07 | 1/2 | [Begripsfout] | Goed dat je de verbinding maakt met de zee, maar wolken vallen niet letterlijk uit de lucht; het water daalt als neerslag. Kijk naar de volledige waterkringloop: verdamping, condensatie en neerslag. |
| L08 | 1/2 | [Vergeet neerslag] | Goed gedaan dat je de stroming via rivieren naar de zee benoemt, maar vergeten te hebben dat het water via neerslag terug de aarde op komt. De volgende stap is om te onthouden dat het water na verdamping en condensatie als regen of sneeuw neerdaalt. |
| L09 | 1/2 | [Begripsfout] | Goed dat je de verdamping als eerste stap noemt, maar let op: verdampt water wordt waterdamp, geen wind. De volgende stap is dat deze damp opstijgt en condenseert tot wolken, waarna het als neerslag terugvalt. |
| L10 | 0/2 | [Vergeet neerslag] | Je hebt goed begrepen dat de waterkringloop een doorlopende cyclus is, maar je miste de cruciale stap van neerslag. Zorg dat je in je uitleg altijd de drie fasen noemt: verdamping, condensatie en neerslag. |
| L11 | 0/2 | [Begripsfout] | Je hebt een interessante link gelegd met de maan, maar dat heeft niets te maken met de waterkringloop. Kijk naar hoe water verdampt, condenseert en als neerslag terugvalt om het proces te snappen. |
| L12 | 0/2 | [Begripsfout] | Dat is een misvatting, want vissen duwen het water niet in de lucht; de waterkringloop werkt door verdamping, condensatie en neerslag. Kijk naar hoe de zon het water laat verdampen om neerslag te vormen. |
| L13 | 0/2 | [Begripsfout] | Het is belangrijk om te beseffen dat water geen gevoelens of honger heeft, maar dat de kringloop wordt aangedreven door natuurlijke processen zoals verdamping, condensatie en neerslag. Concentreer je op hoe de zon het water verdampt en hoe het daarna als neerslag terugkomt op aarde. |
| L14 | 0/2 | [Begripsfout] | Dat is een misverstand: 'waternoom' is geen dier, maar een verouderd woord voor de waterkringloop. De juiste stap is om te begrijpen dat water via verdamping opstijgt, condenseert tot wolken en als neerslag terugvalt. |
| L15 | 0/2 | [Begripsfout] | Dat is een creatief beeld, maar de zon drinkt het water niet; ze verdampt het door warmte. Kijk naar de waterkringloop: de zon verdamp het water, dat in de lucht condenseert tot wolken en als neerslag terugvalt. |
| L18 | 1/2 | [Vergeet condensatie] | Goed dat je de verdamping en neerslag benoemt, maar vergeet niet dat het water eerst moet condenseren tot wolken voordat het als regen naar beneden komt. |
| L19 | 0/2 | [Begripsfout] | Je beschrijft het proces van neerslag, maar water kan niet vanzelf de berg oplopen; het verdampt eerst en stijgt als waterdamp. Kijk naar de waterkringloop: verdamping, condensatie in de lucht en daarna neerslag. |
| L20 | 1/2 | [Vergeet verdamping] | Je hebt goed begrepen dat wolken en regen een belangrijk onderdeel zijn van het proces. De belangrijkste stap is om te onthouden dat water eerst moet verdampen om in de lucht te komen, waarna het condenseert tot wolken en als neerslag terugvalt. |

## Stap 4 — Docent-briefing

## Samenvatting klasprestaties
Van de 20 leerlingen zijn er 18 geldige tickets ingeleverd. De gemiddelde score is 0,78. De verdeling is als volgt: 7 leerlingen scoren 0, 8 leerlingen scoren 1 en 3 leerlingen scoren 2.

**Twijfelgevallen (handmatige controle vereist):**
Het nakijkmodel is onzeker over de score van de volgende leerlingen; de docent kijkt deze zelf na:
*   **L07** (score 1, zekerheid 0,578)
*   **L10** (score 0, zekerheid 0,575)
*   **L19** (score 0, zekerheid 0,486)
*   **L20** (score 1, zekerheid 0,438)

**Ongeldige tickets:**
De volgende leerlingen hebben een ongeldig ticket ingeleverd: L16, L17.

## Veelvoorkomende misvattingen
Op basis van de fouttags uit de geldige tickets zijn dit de meest voorkomende issues:
1.  **Begripsfouten (8x):** Leerlingen beschrijven de kringloop met onjuiste mechanismen of personificaties (bijv. "water honger", "zon drinkt water", "vissen duwen water omhoog", "water loopt berg op"). Dit duidt op een fundamenteel gebrek aan inzicht in de fysieke processen.
2.  **Vergeet condensatie (3x):** Leerlingen springen direct van verdamping naar neerslag, zonder de vorming van wolken te benoemen.
3.  **Vergeet neerslag (3x):** Leerlingen beschrijven de opstijging (verdamping/condensatie) maar vergeten de terugval op aarde.
4.  **Vergeet verdamping (1x):** Leerlingen beginnen bij wolken/regen zonder de oorsprong (verdamping) te noemen.

## Voorstel opening volgende les
**Activiteit: "De Kringloop in 60 seconden" (5-10 minuten)**

*   **Doel:** Directe correctie van de begripsfouten en het verankeren van de volgorde van de drie fasen.
*   **Uitvoering:**
    1.  Schrijf de drie kernwoorden op het bord: **VERDAMPING** – **CONDENSATIE** – **NEERSLAG**.
    2.  Laat leerlingen in paren (of alleen, afhankelijk van de groep) elk een van de drie fasen toelichten met één zin, waarbij ze expliciet moeten uitleggen *wat* er gebeurt (bijv. "Zon verwarmt water, het stoomt op" voor verdamping).
    3.  Vraag twee leerlingen die een 'begripsfout' maakten (bijv. L11 of L12, na handmatige check) om hun eerdere uitleg te corrigeren met behulp van de drie woorden op het bord.
    4.  Sluit af met een snelle check: "Welke fase ontbreekt in deze zin: 'Water verdampt en regent weer'?" (Antwoord: Condensatie).

*   **Waarom dit werkt:** Het forceert de juiste volgorde en de juiste terminologie, en confronteert de leerlingen direct met hun eigen misvattingen in een lage drempelsetting.

## Aggegreerde data (JSON die naar Qwen werd gestuurd)

```json
{
  "exit_ticket_vraag": "Leg in maximaal 3 zinnen uit hoe de waterkringloop werkt. Noem minimaal drie fasen.",
  "klas": {
    "aantal_leerlingen": 20,
    "geldig": 18,
    "ongeldig": 2,
    "ongeldige_ids": [
      "L16",
      "L17"
    ]
  },
  "scores": {
    "gemiddeld": 0.78,
    "verdeling": {
      "0": 7,
      "1": 8,
      "2": 3
    }
  },
  "fout_tags": {
    "[Begripsfout]": 8,
    "[Geen fout]": 3,
    "[Vergeet condensatie]": 3,
    "[Vergeet neerslag]": 3,
    "[Vergeet verdamping]": 1
  },
  "twijfelgevallen": [
    {
      "id": "L07",
      "score": 1,
      "zekerheid": 0.578
    },
    {
      "id": "L10",
      "score": 0,
      "zekerheid": 0.575
    },
    {
      "id": "L19",
      "score": 0,
      "zekerheid": 0.486
    },
    {
      "id": "L20",
      "score": 1,
      "zekerheid": 0.438
    }
  ],
  "leerlingen": [
    {
      "id": "L01",
      "score": 2,
      "fout_tag": "[Geen fout]",
      "zekerheid_score": 0.857,
      "antwoord": "Water verdampt door de warmte van de zon, kondenseert in de hoge lucht tot wolken en valt als neerslag, regen of sneeuw, terug op aarde.",
      "feedback": "Mooi gedaan, je beschrijft de volledige waterkringloop perfect. Je hebt alle drie de belangrijke fasen, namelijk verdamping, condensatie en neerslag, correct aan elkaar gekoppeld."
    },
    {
      "id": "L02",
      "score": 2,
      "fout_tag": "[Geen fout]",
      "zekerheid_score": 0.883,
      "antwoord": "De waterkringloop bestaat uit verdamping, condensatie en neerslag. Water stoomt op uit zeeën, wordt wolken en regent of sneuvelt weer naar beneden.",
      "feedback": "Mooi gedaan, je beschrijft de drie fasen van de waterkringloop precies en in de juiste volgorde. Je hebt de stof volledig onder de knie en bent klaar voor de volgende stap."
    },
    {
      "id": "L03",
      "score": 2,
      "fout_tag": "[Geen fout]",
      "zekerheid_score": 0.767,
      "antwoord": "Het water gaat omhoog als damp, maakt wolken en dan regent het weer.",
      "feedback": "Prima, je beschrijft de volledige waterkringloop exact in de juiste volgorde. Je hebt de stof volledig onder de knie."
    },
    {
      "id": "L04",
      "score": 1,
      "fout_tag": "[Vergeet condensatie]",
      "zekerheid_score": 0.794,
      "antwoord": "Water verdamp en dan regent het weer op de grond.",
      "feedback": "Goed dat je de verdamping en neerslag benoemt, maar vergeet niet dat waterdamp eerst moet condenseren tot wolkjes voordat het kan regenen. Probeer de volledige cyclus te benoemen: verdamping, condensatie en neerslag."
    },
    {
      "id": "L05",
      "score": 1,
      "fout_tag": "[Vergeet condensatie]",
      "zekerheid_score": 0.766,
      "antwoord": "Eerst valt er neerslag uit de lucht en daarna verdampt het water weer in de oceaan.",
      "feedback": "Je hebt goed begrepen dat neerslag en verdamping deel uitmaken van de kringloop, maar je bent de stap condensatie vergeten. Probeer de volgorde te corrigeren door te bedenken dat het water eerst moet condenseren tot wolkjes voordat het als neerslag naar beneden kan vallen."
    },
    {
      "id": "L06",
      "score": 1,
      "fout_tag": "[Vergeet neerslag]",
      "zekerheid_score": 0.736,
      "antwoord": "De zon verwarmt het water in de zee en dat komt omhoog als wolken in de lucht.",
      "feedback": "Goed gedaan dat je de verdamping en condensatie correct beschrijft, maar vergeet niet dat het water na de wolken als neerslag weer naar beneden valt. Kijk even goed naar de volledige kringloop: verdamping, condensatie en neerslag."
    },
    {
      "id": "L07",
      "score": 1,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.578,
      "antwoord": "Wolken vallen uit de lucht en dan stroomt het water in de zee.",
      "feedback": "Goed dat je de verbinding maakt met de zee, maar wolken vallen niet letterlijk uit de lucht; het water daalt als neerslag. Kijk naar de volledige waterkringloop: verdamping, condensatie en neerslag."
    },
    {
      "id": "L08",
      "score": 1,
      "fout_tag": "[Vergeet neerslag]",
      "zekerheid_score": 0.703,
      "antwoord": "Het water stroomt via rivieren naar de zee en komt dan weer terug in de lucht.",
      "feedback": "Goed gedaan dat je de stroming via rivieren naar de zee benoemt, maar vergeten te hebben dat het water via neerslag terug de aarde op komt. De volgende stap is om te onthouden dat het water na verdamping en condensatie als regen of sneeuw neerdaalt."
    },
    {
      "id": "L09",
      "score": 1,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.634,
      "antwoord": "Als het warm is dan verdampt het water en dat wordt dan wind die de wolken door de lucht duwt.",
      "feedback": "Goed dat je de verdamping als eerste stap noemt, maar let op: verdampt water wordt waterdamp, geen wind. De volgende stap is dat deze damp opstijgt en condenseert tot wolken, waarna het als neerslag terugvalt."
    },
    {
      "id": "L10",
      "score": 0,
      "fout_tag": "[Vergeet neerslag]",
      "zekerheid_score": 0.575,
      "antwoord": "De waterkringloop is een soort kring van water die altijd door blijft gaan.",
      "feedback": "Je hebt goed begrepen dat de waterkringloop een doorlopende cyclus is, maar je miste de cruciale stap van neerslag. Zorg dat je in je uitleg altijd de drie fasen noemt: verdamping, condensatie en neerslag."
    },
    {
      "id": "L11",
      "score": 0,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.941,
      "antwoord": "Ik denk dat het te maken heeft met de maan, want het water gaat omhoog en omlaag.",
      "feedback": "Je hebt een interessante link gelegd met de maan, maar dat heeft niets te maken met de waterkringloop. Kijk naar hoe water verdampt, condenseert en als neerslag terugvalt om het proces te snappen."
    },
    {
      "id": "L12",
      "score": 0,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.978,
      "antwoord": "Omdat vissen het water in de lucht duwen met hun staarten.",
      "feedback": "Dat is een misvatting, want vissen duwen het water niet in de lucht; de waterkringloop werkt door verdamping, condensatie en neerslag. Kijk naar hoe de zon het water laat verdampen om neerslag te vormen."
    },
    {
      "id": "L13",
      "score": 0,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.94,
      "antwoord": "De waterkringloop bestaat omdat het water honger heeft naar de aarde.",
      "feedback": "Het is belangrijk om te beseffen dat water geen gevoelens of honger heeft, maar dat de kringloop wordt aangedreven door natuurlijke processen zoals verdamping, condensatie en neerslag. Concentreer je op hoe de zon het water verdampt en hoe het daarna als neerslag terugkomt op aarde."
    },
    {
      "id": "L14",
      "score": 0,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.84,
      "antwoord": "Waternoom is een dier dat in de zee woont en dat spuilt dan het water de lucht in.",
      "feedback": "Dat is een misverstand: 'waternoom' is geen dier, maar een verouderd woord voor de waterkringloop. De juiste stap is om te begrijpen dat water via verdamping opstijgt, condenseert tot wolken en als neerslag terugvalt."
    },
    {
      "id": "L15",
      "score": 0,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.907,
      "antwoord": "Omdat de zon 's nachts het water drinkt en 's ochtends weer brukt op de aarde.",
      "feedback": "Dat is een creatief beeld, maar de zon drinkt het water niet; ze verdampt het door warmte. Kijk naar de waterkringloop: de zon verdamp het water, dat in de lucht condenseert tot wolken en als neerslag terugvalt."
    },
    {
      "id": "L18",
      "score": 1,
      "fout_tag": "[Vergeet condensatie]",
      "zekerheid_score": 0.785,
      "antwoord": "In de zee wordt water verdampt en dan regent het weer op de bergen.",
      "feedback": "Goed dat je de verdamping en neerslag benoemt, maar vergeet niet dat het water eerst moet condenseren tot wolken voordat het als regen naar beneden komt."
    },
    {
      "id": "L19",
      "score": 0,
      "fout_tag": "[Begripsfout]",
      "zekerheid_score": 0.486,
      "antwoord": "Het water loopt langzaam de berg op en dan valt het er weer van af als regen.",
      "feedback": "Je beschrijft het proces van neerslag, maar water kan niet vanzelf de berg oplopen; het verdampt eerst en stijgt als waterdamp. Kijk naar de waterkringloop: verdamping, condensatie in de lucht en daarna neerslag."
    },
    {
      "id": "L20",
      "score": 1,
      "fout_tag": "[Vergeet verdamping]",
      "zekerheid_score": 0.438,
      "antwoord": "Iets met wolken en regen, maar ik weet de fases niet echt te benoemen.",
      "feedback": "Je hebt goed begrepen dat wolken en regen een belangrijk onderdeel zijn van het proces. De belangrijkste stap is om te onthouden dat water eerst moet verdampen om in de lucht te komen, waarna het condenseert tot wolken en als neerslag terugvalt."
    }
  ]
}
```

---
_Gegenereerd door `clef-tev-demo/pipeline.py` in 128s totaal. Regenereer met: `python pipeline.py`_