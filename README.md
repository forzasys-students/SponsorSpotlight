# SponsorSpotlight

Dette prosjektet er en webapplikasjon som analyserer sponsorlogoer i videoinnhold ved hjelp av AI-modellen YOLOv11.

## 📥 Kloning av prosjektet

Du kan laste ned prosjektet ved å bruke en av følgende metoder:

### 🔹 Metode 1: GitHub Desktop (anbefalt)

1. Gå til GitHub-repositoriet:  
   https://github.com/forzasys-students/SponsorSpotlight
2. Trykk på den grønne **Code**-knappen og velg **"Open with GitHub Desktop"**.
3. Velg ønsket mappe lokalt og trykk **Clone**.
4. Når prosjektet er klonet, trykk på **"Open in Visual Studio Code"** for å åpne prosjektet.

### 🔹 Metode 2: Kommandolinje

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

Dersom du ikke har Python installert, last det ned fra: https://www.python.org/

3. Naviger til `app`-mappen:

```bash
cd app
```

4. Installer alle avhengigheter:

```bash
pip install -r requirements.txt
```

## 🚀 Kjøring av applikasjonen

Etter at avhengighetene er installert:

1. Gå tilbake til rotmappen:

```bash
cd ..
```

2. Start applikasjonen:

```bash
python -m app.app
```

3. Følg lenken i terminalen (f.eks. `http://127.0.0.1:5000`) for å åpne applikasjonen i nettleseren.

## 💡 Bruk av applikasjonen

Når applikasjonen er startet i nettleseren, får du opp et enkelt webgrensesnitt.

Her kan du:
- 📁 Laste opp en videofil fra maskinen
- 🌐 Lime inn en M3U8-lenke til en videostrøm

Trykk deretter på **Submit**. Applikasjonen vil:
- Ekstrahere bilder fra videoen
- Bruke en trenet AI-modell (YOLOv11) for å gjenkjenne sponsorlogoer
- Vise fremgang i sanntid

## 📊 Resultatvisning og eksport

Etter at videoen er analysert:
- En videospiller vises
- Du kan filtrere på spesifikke sponsorer
- Trykk på **Scroll to diagram** for å hoppe til visualiseringen

Diagrammet viser:
- Prosentvis eksponering
- Antall rammer logoen ble sett i
- Tid (i sekunder)

Du kan også laste ned statistikken som Excel-fil med knappen **Export to Excel**.
