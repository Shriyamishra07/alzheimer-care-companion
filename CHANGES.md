# Changes after the guide's feedback (version 0.7)

Same platform as in the report and paper: React + Vite web app, FastAPI, PostgreSQL (Neon), Gemini (optional),
OpenStreetMap, Docker on Render. No new services. All 60 automated tests pass (40 earlier + 20 new), and the
grounding evaluation gives exactly the numbers in the report (NFR-AI-1 to 6 met, 28 of 28 answers correct).

## 1. Sign-in redesign

* **Why it was hard to find:** on phones the website hid the header's "Sign in" button, so the only way in was a
  link at the very bottom of the page.
* **Now:** "Sign in" and "Get started" are in the header on every screen size, and a sign-in card is part of the
  website's first screen. On a phone it comes straight after the headline.
* **`/login` page:** new split-screen design. It has a brand panel, Sign in / Create account tabs, large role
  cards ("I'm saving my memories" / "I care for someone"), a show-password button and one-tap demo accounts.

## 2. Primary caregiver and access control

* **Who is primary:** the first caregiver to link becomes the **primary caregiver**.
* **What the primary (or the person) can do:**
  * invite other caregivers with a one-time code, choosing what each of them can see;
  * change any caregiver's access later;
  * remove a caregiver;
  * hand the primary role to someone else.
* **The six permissions:** memories and daily activity, places and location (including where a Help alert came
  from), reminders, sending messages, adding memories, and Help alerts.
* **Enforced on the server:** a caregiver who asks for something not shared with them gets a 403 refusal, whatever
  the app shows. Private memories are never shown to anyone.
* **Recorded:** every change (invited, access changed, removed, new primary) appears in the person's
  "Who saw my data".
* **No surprise promotion:** if the primary caregiver is removed, nobody is promoted automatically. The person
  chooses the next primary, so a limited caregiver never gets full access by surprise.
* **Screens:** caregiver: **Care team** (new tab). Person: **Family and care team**.

## 3. Voice-based reminders

* **Reminder types:** medicine, activity, appointment or other.
* **Scheduling:** daily, or one time on a date (appointments), with an optional note.
* **When a reminder is due:** a full-screen reminder appears and is **read aloud**. If a family member recorded a
  **voice message**, that recording plays instead. The buttons are **Done** and **Remind me in 10 minutes**.
* **In the background:** with permission, a phone notification also appears.
* **Dictation:** reminders can be dictated with the microphone button instead of typed.
* **Who can add them:** caregivers with the reminders permission can add reminders and record the voice message
  from their dashboard.

## 4. LLM data privacy and security

* **Redaction:** before any text is sent to Gemini, the server replaces names, places, phone numbers, emails,
  Aadhaar, PAN and card numbers with tokens (for example `PERSON_12`, `PLACE_3`, `PHONE_8f2a`). The model only
  sees the tokens. The real words are put back on the server, and the mapping never leaves it.
* **Proof in the tests:** a test replaces Gemini with a fake that records every request, and checks that no name,
  place or phone number gets through (`tests/test_features.py`).
* **Photos and voice notes:** these cannot be redacted like text, so describing them with the AI is **off unless
  the person switches it on**.
* **Photo metadata:** EXIF data, including GPS position, is removed from photos on the server.
* **Audit trail:** every request to the AI is stored in redacted form in the query log.
* **On screen:** the Ask page can show exactly what the AI received, and the **Privacy and AI** page has a live
  "See what the AI receives" preview.

## How to demo it to the guide

1. **Phone sign-in:** open the website on a phone. Sign-in is at the top, and the sign-in card is in the first
   screen.
2. **Primary caregiver:** use the demo **Anita** (primary caregiver) and open **Care team**. Switch one of
   **Rohan**'s permissions on or off, or create an invite code.
3. **Limited caregiver:** use the demo **Rohan** (limited caregiver). The dashboard shows only what Anita shares.
   Memories and places are hidden, and the server refuses them too.
4. **Voice reminder:** use the demo **Suresh**, open **Reminders** and add a reminder for the current minute. The
   full-screen reminder appears and speaks. Tap **Hear a test reminder** first if the browser blocks sound.
5. **AI privacy:** as **Suresh**, open **Privacy and AI**, then press "Show what the AI would receive".

## Upgrading the live site

Push to GitHub and Render redeploys. The database is upgraded automatically at startup (`backend/app/migrate.py`
adds the new columns), and existing data is kept. The earliest caregiver of each person becomes the primary. The
demo gains Rohan and an appointment reminder.

## Known limits (honest)

* **When reminders fire:** they work while the app is open or running in the background. Render's free plan
  sleeps when idle, so push notifications to a fully closed app would need an always-on server or the native
  Android build planned for Semester VIII.
* **Free Gemini tier:** Google may use the data it receives on the free tier. Redaction reduces what it sees, but
  real use should move to the paid tier.
* **Limits of redaction:** it removes the names the app knows (people, places, family, the person's own name) and
  common ID formats. A name the person never saved anywhere, typed in free text, can still get through.
