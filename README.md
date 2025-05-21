# SponsorSpotlight

SponsorSpotlight er en webapplikasjon som analyserer sponsorlogoer i videoinnhold ved hjelp av AI-modellen YOLOv11. Applikasjonen støtter både lokal videoopplasting og sanntidsanalyse av videostrømmer via M3U8-lenker.

![Eksempel Deteksjon](example-detection.gif)

---

## 📦 Kloning av prosjektet

For å laste ned kildekoden til prosjektet finnes det tre ulike metoder: bruk av GitHub Desktop, bruk av kommandolinjen med Git, eller nedlasting som en ZIP-fil direkte fra GitHub.

### Metode 1: GitHub Desktop

1. Gå til GitHub-repositoriet:  
2. Trykk på den grønne `Code`-knappen og velg **Open with GitHub Desktop**.
3. Velg ønsket lokal mappe og trykk **Clone**.
4. Når kloningen er fullført, åpne prosjektet i VS Code med **Open in Visual Studio Code**.

### Metode 2: Kommandolinje

```bash
git clone https://github.com/forzasys-students/SponsorSpotlight.git
cd SponsorSpotlight
code .
```

### Metode 3: Nedlasting som ZIP-fil

1. Gå til GitHub-repositoriet
2. Trykk på den grønne `Code`-knappen og velg **Download ZIP**.
3. Pakk ut filen på ønsket sted.
4. Åpne mappen i VS Code ved å høyreklikke og velge **Open with Code**, eller via File → Open Folder i VS Code.

---

## 🧩 Installering av avhengigheter

Før applikasjonen kan kjøres, må nødvendige avhengigheter installeres. Disse er spesifisert i `requirements.txt`.

1. Åpne terminal i VS Code.
2. Sjekk at Python og pip er installert:

```bash
python --version
pip --version
```

✅ Hvis disse ikke fungerer, prøv:

```bash
python3 --version
pip3 --version
```

🔗 Hvis Python ikke er installert, last det ned fra: https://www.python.org/

3. Naviger inn i `app`-mappen:

```bash
cd app
```

4. Installer nødvendige biblioteker:

```bash
pip install -r requirements.txt
# eller
pip3 install -r requirements.txt
```

---

## 🚀 Kjøring av programmet

1. Gå tilbake til rotmappen hvis du står i `app`-mappen:

```bash
cd ..
```

2. Start applikasjonen:

```bash
python -m app.app
# eller
python3 -m app.app
```

Etter oppstart vil det vises en lokal nettadresse (f.eks. `http://127.0.0.1:5000`).  
Hold inne `Ctrl` (eller `Cmd` på Mac) og klikk på lenken, eller lim den inn i nettleseren manuelt.

---

## 🖥️ Bruk av applikasjonen

Etter at nettsiden er åpnet, kan du:

- **Laste opp lokal videofil** – Klikk på *Choose File* og velg en videofil.
- **Lim inn M3U8-lenke** – Lim inn lenken til en ekstern videostrøm.

Når du trykker på **Submit**, starter applikasjonen en AI-basert analyse ved hjelp av YOLOv11. Logoeksponering identifiseres bilde for bilde.

---

## 📊 Resultat og eksport

Etter analysen vises resultatene i tre trinn:

1. **Videovisning** med annoterte rammer.
2. **Filtreringsmeny** for valg av sponsorer.
3. **Scroll to Diagram** – fører til et interaktivt diagram.

Diagrammet viser hvor ofte og hvor lenge hver logo har vært synlig.  
Resultatene kan eksporteres som en Excel-fil via knappen **Export to Excel**.

---

## 🛠️ Teknologier brukt

- Python 3.x  
- Flask  
- YOLOv11 (Ultralytics)  
- OpenCV  
- NumPy  
- FFmpeg  
- HTML, CSS, JavaScript

---

🧪 *SponsorSpotlight er utviklet som en del av en bacheloroppgave i Anvendt Datateknologi ved OsloMet, 2025.*
