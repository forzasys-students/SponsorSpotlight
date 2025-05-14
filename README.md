
# SponsorSpotlight

Dette prosjektet er en webapplikasjon som analyserer sponsorlogoer i videoinnhold ved hjelp av AI-modellen YOLOv11. Applikasjonen støtter både lokal videoopplasting og sanntidsanalyse av videostrømmer via M3U8-lenker.

![Eksempel Deteksjon](example-detection1.gif)

## 📦 Kloning av prosjektet

Du kan klone prosjektet med én av følgende metoder:

### Metode 1: GitHub Desktop (anbefalt)

1. Gå til GitHub-repositoriet: [https://github.com/forzasys-students/SponsorSpotlight](https://github.com/forzasys-students/SponsorSpotlight)
2. Trykk på den grønne `Code`-knappen og velg **Open with GitHub Desktop**.
3. Velg ønsket lokal mappe og trykk **Clone**.
4. Åpne prosjektet i VS Code med **Open in Visual Studio Code**.

### Metode 2: Kommandolinje

```bash
git clone https://github.com/forzasys-students/SponsorSpotlight.git
cd SponsorSpotlight
code .
```

## 🧩 Installering av avhengigheter

Applikasjonen avhenger av flere Python-biblioteker. Disse kan installeres slik:

1. Åpne terminal i VS Code.
2. Sjekk at python og pip er installert:

```bash
python --version 
pip --version
```

✅ Hvis disse kommandoene ikke fungerer, kan du også prøve:

```bash
python3 --version
pip3 --version
```

3. Naviger inn i `app`-mappen:

```bash
cd app
```

4. Installer alle nødvendige avhengigheter:

```bash
pip install -r requirements.txt
```

eller (om du bruker python3/pip3):

```bash
pip3 install -r requirements.txt
```

## 🚀 Kjøring av programmet

1. Gå tilbake til rotmappen hvis du står i `app`-mappen:

```bash
cd ..
```

2. Start applikasjonen:

```bash
python -m app.app
```

Eller (hvis du bruker python3):

```bash
python3 -m app.app
```

Etter oppstart vil det vises en lokal nettadresse (som f.eks. `http://127.0.0.1:5000`). Hold inne `Ctrl` og klikk på lenken, eller lim den inn i nettleseren din.

## 🖥️ Bruk av applikasjonen

Etter at nettsiden er åpnet, kan du:

- **Laste opp lokal videofil** – Klikk på *Choose File* og velg en fil.
- **Lim inn M3U8-lenke** – Bruk en lenke til en videostrøm på nett.

Etter å ha valgt videokilde og trykket på **Submit**, starter applikasjonen en AI-basert analyse (YOLOv11). Logoeksponering identifiseres bilde for bilde.

## 📊 Resultat og eksport

Etter analyse vises resultater i tre trinn:

1. **Videovisning** med annoterte rammer.
2. **Filtreringsmeny** for valg av sponsorer.
3. **Scroll to Diagram** sender deg ned til et interaktivt diagram.

Diagrammet viser hvor ofte og hvor lenge hver logo har vært synlig. Du kan eksportere resultatene som en Excel-fil med **Export to Excel**.

## 🛠️ Teknologier brukt

- Python 3.x
- Flask
- YOLOv11 (Ultralytics)
- OpenCV
- NumPy
- FFmpeg (for M3U8-strømmer)
- HTML, CSS, JavaScript (frontend)

---

🧪 *SponsorSpotlight er utviklet som en del av en bacheloroppgave i Anvendt Datateknologi ved OsloMet, 2025.*
