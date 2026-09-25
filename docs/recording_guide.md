# Recording guide — 3–5 minute demo

Everything you need to record the submission video. Target length **~4 minutes**.
Read this off your phone while you record on the Mac.

---

## A. Before you hit record (pre-flight, 5 min)

1. **Clean the run so it's fresh on camera** (optional but nice):
   ```bash
   cd /Users/raamtichkule/FDE_Assignment_1/nyc-tlc-pipeline
   rm -rf outputs build logs
   ```
   (The raw file stays cached, so the live run stays fast.)

2. **Open these tabs/windows in advance** so you're not fumbling:
   - A **terminal** already in the project folder.
   - Your editor (Kiro/VS Code) showing the repo tree, with these files ready to click:
     `docs/source_map.md`, `src/validate.py`, `docs/data_model.md`.
   - A **browser** (you'll open the dashboard URL live).

3. **Zoom your terminal + editor font up** (Cmd-+) so text is readable on video.

4. **Close notifications** — turn on Do Not Disturb (Control Center → Focus).

5. **Test your mic** once (say a sentence, play it back).

---

## B. How to record on macOS

**Easiest: built-in recorder**
1. Press **Shift-Cmd-5**.
2. Click **Options** → under *Microphone* pick your mic (so your voice records).
3. Choose **Record Entire Screen** (or *Selected Portion* for just the window).
4. Click **Record**. Do the demo. Stop from the menu bar icon (or Shift-Cmd-5 → Stop).
5. The `.mov` saves to your Desktop. Trim start/end in QuickTime (Edit → Trim) if needed.

**If you want webcam-in-corner + easy trimming:** use QuickTime (File → New Screen
Recording) plus **Photo Booth**, or a free tool like OBS. Not required — screen +
voice is enough.

**Keep the file small:** 1080p is plenty. If it's huge, compress in QuickTime
(File → Export As → 720p).

---

## C. The script (what to show + say, timed)

> Speak calmly. It's fine to pause the recording between sections and stitch, but
> a single take is more natural. Total ≈ 4:00.

### 0:00–0:20 · Framing
**On screen:** README top.
**Say:**
> "This is a data pipeline for a taxi fleet operations team. The data is messy and
> self-reported, so my goal isn't just to analyse it — it's to build a trustworthy,
> repeatable path from raw files to metrics leadership can act on. My KPI is fleet
> efficiency and data trust: can we rely on this month, and where is the fleet slow?"

### 0:20–0:55 · Sources & retrieval
**On screen:** open `docs/source_map.md`.
**Say:**
> "There are two sources: the monthly trip file and a zone lookup that maps location
> IDs to boroughs. I retrieve them two ways — as files over HTTP, and then query them
> with DuckDB SQL. I don't assume the download is complete: I compare the row count in
> the file's own metadata against what the database actually reads, and record a
> checksum for provenance."

### 0:55–1:55 · Live run + the guardrail
**On screen:** terminal.
**Type:**
```bash
.venv/bin/python -m src.pipeline --period 2024-01
```
**Say (while it runs ~6s):**
> "One command runs the whole thing — ingest, validate, model, metrics — each stage
> timed and logged. Here: 2.96 million raw trips, 90.6% passed validation."

**Then show the safety check. Type:**
```bash
.venv/bin/python -m src.pipeline --period 2024-01 --min-valid-rate 0.99
```
**Say:**
> "And it fails safe. If I demand 99% valid and the data can't meet it, the pipeline
> refuses to publish and exits with an error, instead of handing leadership numbers
> nobody should trust."

### 1:55–2:35 · Validation, not silent cleaning
**On screen:** open `outputs/data_quality_report_2024-01.csv`.
**Say:**
> "This is the part I care most about. I don't silently delete bad rows — I quarantine
> them with a reason and report every rule. The biggest rejection is bad passenger
> count at 5.8%, then impossible average speeds. The rejected rows are kept for audit,
> not thrown away."

### 2:35–3:35 · THE JUDGEMENT CALL (the graded moment)
**On screen:** open the dashboard —
```bash
.venv/bin/streamlit run app.py
```
open the printed URL, point at the **borough scatter**.
**Say:**
> "Here's the judgement call I want to highlight. The headline median speed is about
> 9.6 mph. On its own, that's misleading. Look at the breakdown: Manhattan trips are
> short and slow — that's congestion — while Queens trips are long and fast, because
> those are airport runs. A single citywide average hides two totally different
> operating regimes. So I always report the speed *with* this borough breakdown —
> otherwise ops would add supply in the wrong place. Reporting a number with the
> context that makes it safe to act on: that's the FDE call."

### 3:35–4:00 · Dependability & close
**On screen:** back to terminal, scroll the log; mention Jan + Feb outputs exist.
**Say:**
> "It's repeatable: reruns reuse the cached raw file by checksum, and I ran it for both
> January and February with the same code and one flag. And the dashboard only reads
> the pipeline's outputs — it never recomputes — so what you see is exactly what was
> validated. From messy client files to a trustworthy, repeatable decision. Thanks."

---

## D. The one line to nail if they ask "what was your key judgement call?"

> "Reporting median trip speed **only alongside the pickup-borough breakdown**,
> because the citywide median blends congested Manhattan trips with fast Queens
> airport runs — acting on the blended number would put supply in the wrong place."

---

## E. Common gotchas
- If the dashboard says "no outputs found," you deleted `outputs/` and haven't rerun
  the pipeline yet — run it once first.
- Streamlit prints the real URL (usually `http://localhost:8501`); use whatever it shows.
- To stop the dashboard after recording: press **Ctrl-C** in that terminal.
- Don't show any secrets/tokens on screen (there are none in this project, but check
  your terminal scrollback before recording).
