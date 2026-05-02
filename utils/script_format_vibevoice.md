# VibeVoice Script Format

The Script Writer and Editor agents produce a single **source script** (see
[Source script syntax](#source-script-syntax) below). That same source is
rendered to two targets — VibeVoice plain text (this document) and Azure
SSML ([script_format_azure_ssml.md](script_format_azure_ssml.md)).

This file covers:

1. The shared source-script syntax the writer/editor produce.
2. How that source is converted into a VibeVoice-compatible `.txt` file.
3. The native VibeVoice format reference (what the renderer must emit).

---

## Source script syntax

Plain UTF-8 text. One turn per non-empty line. The writer and editor both
read and emit this format.

### Structural elements

```
[Section Name]               ← full-line bracket = section header (e.g. [Cold Open])
HostName: spoken text…       ← turn line
[Editor's Notes]             ← marks the start of a notes block (stops the script)
- bullet
- bullet
```

- **Section headers** are full-line bracket markers (`[Cold Open]`,
  `[Segment 1: ...]`, `[Outro]`). They are structural only — discarded by
  both renderers.
- **Turn lines** are `HostName: text`. The host-name → voice mapping is
  configured once at render time (see "Host mapping" below); the script
  itself never names a voice.
- **Editor's Notes** is a sentinel — every line from `[Editor's Notes]`
  onward is dropped by both renderers.

### Inline inflection cues

Cues live inside a turn line, between the colon and the end of the line.

| Cue                          | Syntax                            | Span                                          |
|------------------------------|-----------------------------------|-----------------------------------------------|
| Style / emotion              | `[style-name]`                    | until the next `[…]` on this line, or EOL     |
| Paralinguistic (HD only)     | `[laughter]` `[sighing]` etc.     | momentary — applies to the immediate phrase   |
| Pause                        | `(pause)` or `(pause:300ms)`      | point insertion                               |
| Rate                         | `(rate:slow)` / `(rate:fast)`     | until the next `(rate:…)` on this line, or EOL |
| Volume                       | `(volume:soft)` / `(volume:loud)` | until the next `(volume:…)` on this line, or EOL |
| Word emphasis                | `**word**`                        | the bracketed word(s)                         |
| Inline foreign phrase        | `[lang:fr-FR]bonjour[/lang]`      | between the open and close                    |

Disambiguation: a line that is **only** `[X]` (with no spoken text after)
is a section header. A `[X]` cue followed by spoken text on the same line
is an inflection cue. Writers must always put spoken text on the same line
as a cue.

Style names — see the SSML doc for the full lists. The writer should
default to neural-voice styles (`chat`, `cheerful`, `serious`,
`narration-professional`, etc.) unless the producer has selected an HD
voice, in which case the HD style list and paralinguistics
(`[laughter]`, `[sighing]`, `[breathing]`) become available.

### Example source

```
[Cold Open]
Ken: [serious] The hatch in season two — (pause:300ms) everyone remembers
the countdown, nobody remembers the lie underneath it.
Maya: [chat] The lie?
Ken: [serious] Well actually, the button isn't doing what they think it's
doing. (pause) That's the whole game.
Maya: [unfriendly] Says who? The Dharma orientation tape literally says
**push the button**.
Ken: (rate:slow) Sort of, but… (pause:400ms) the tape is the lie.
```

---

## Source → VibeVoice conversion

VibeVoice has **no markup language**. It conditions delivery on the
reference voice, on natural punctuation, and on word choice. Every
inflection cue in the source is therefore stripped — VibeVoice rendering
is *lossy by design*.

Conversion rules (apply in order):

1. **Truncate at notes.** Drop everything from the first line matching
   `^\[Editor` onward.
2. **Drop section headers.** Drop any line matching `^\[.+\]\s*$`.
3. **Drop style/paralinguistic cues.** Remove inline `[style-name]`,
   `[laughter]`, etc. from each turn line, but keep the surrounding text.
4. **Drop prosody cues.** Remove `(pause)`, `(pause:Nms)`, `(rate:…)`,
   `(volume:…)`. Don't replace with anything — punctuation in the
   surrounding text already shapes pacing.
5. **Strip emphasis markers.** `**word**` → `word`. Also strip any stray
   single-asterisk italics from the source.
6. **Strip lang wrappers.** `[lang:xx-XX]text[/lang]` → `text`.
   (VibeVoice may mispronounce; that's the writer's call.)
7. **Drop sound-effect markers** like `[sfx:…]` entirely — VibeVoice
   cannot embed external audio.
8. **Map host names → speaker numbers.** Replace `Ken:` with `Speaker 1:`,
   `Maya:` with `Speaker 2:`, etc., according to the mapping passed to
   the renderer. Maintain a stable order across the whole script.
9. **Collapse blank lines.** Reduce runs of 3+ blank lines to a single
   blank line. The model prefers one turn per line with no empty lines
   between turns.
10. **Re-chunk long monologues.** If a single turn exceeds ~50 words,
    split it into multiple consecutive lines with the same speaker label.
    Break at sentence boundaries.

The result is a file in the **native VibeVoice format** described below.

### Mapping example

Input source:

```
Ken: [serious] Well actually, the button isn't doing what they think it's
doing. (pause) That's the whole game.
Maya: [unfriendly] Says who? The Dharma orientation tape literally says
**push the button**.
```

VibeVoice output (with `Ken=Speaker 1`, `Maya=Speaker 2`):

```
Speaker 1: Well actually, the button isn't doing what they think it's doing. That's the whole game.
Speaker 2: Says who? The Dharma orientation tape literally says push the button.
```

---

## Native VibeVoice format reference

VibeVoice (1.5B / 7B) is a plain-text TTS model. The renderer's output
must conform to the spec below. Reference:
https://github.com/microsoft/VibeVoice

### File format

- A single UTF-8 `.txt` file.
- One turn per line. Each line begins with a speaker label, then a colon,
  then the spoken text.
- Lines separated by a single newline. Do **not** add blank lines between
  turns.
- Up to **4 distinct speakers** per file (1.5B and 7B). Total audio
  length up to ~90 minutes.

### Speaker labels

Use `Speaker 1:`, `Speaker 2:`, `Speaker 3:`, `Speaker 4:` — numbered,
1-indexed, exact casing, single space after "Speaker", colon then a
single space before the text.

```
Speaker 1: Hey, remember "See You Again"?
Speaker 2: Yeah… from Furious 7, right? That song always hits deep.
Speaker 1: Let me try to sing a part of it for you.
```

### Host mapping

The mapping from `Speaker N` to a real voice is supplied at inference
time via the `--speaker_names` CLI flag (e.g.
`--speaker_names Alice Frank` → `Speaker 1=Alice`, `Speaker 2=Frank`).
The script itself never names voices.

Pre-trained voices: `Alice` (en, woman), `Carter` (en, man), `Frank`
(en, man), `Maya` (en, woman), `Mary` (en, woman, includes BGM),
`Samuel` (in, man), `Anchen` (zh, man, BGM), `Bowen` (zh, man),
`Xinran` (zh, woman). Custom voices: pass any name and supply a
matching reference audio sample for voice cloning.

### Multi-turn / multi-voice

Alternate speakers freely across consecutive lines. The model handles
turn-taking and prosody between speakers natively — do not add
transition cues.

If a single speaker has a long monologue and the rendered voice speeds
up, **chunk it across multiple consecutive lines with the same label**:

```
Speaker 1: Here's the thing about the hatch.
Speaker 1: It's not really about the button at all.
Speaker 1: The button is a test of faith, dressed up as a science experiment.
```

### Speaking styles, tones, emotion

VibeVoice has **no style tags, no SSML, no bracketed cues**. It
conditions on:

1. **Punctuation** — `?` raises pitch, `!` adds energy, `…` and `,` add
   pauses, `—` adds a beat, `.` lands a sentence.
2. **Word choice and content** — write the way you want it to sound. "I
   whispered" or "she screamed" inside narration is ignored; instead,
   write short clipped sentences for tension or long flowing ones for
   calm.
3. **Reference voice** — emotional baseline (warm, dry, energetic) comes
   from the speaker's reference audio sample, not from the script.

Do **not** emit tags like `[whispering]`, `[laughs]`, `<emphasis>`, or
stage directions in parentheses in the rendered VibeVoice file. They
will be read aloud literally. (The conversion step above strips them.)

To shape delivery, the source-script writer can lean on:

- Ellipses for hesitation: `Well… I'm not sure.`
- Em dashes for interruption or beat: `It was — and this is the wild
  part — exactly the same hatch.`
- Repetition for emphasis: `No. No, no, no.`
- Short sentences for urgency, longer ones for reflection.
- Onomatopoeia or written-out laughter when a sound is wanted: `Ha. Right.`

These survive the conversion intact, since they're plain punctuation and
word choice rather than tags.

### Native example

```
Speaker 1: Cold open. The hatch in season two — everyone remembers the
countdown, nobody remembers the lie underneath it.
Speaker 2: The lie?
Speaker 1: Well actually, the button isn't doing what they think it's doing.
That's the whole game.
Speaker 2: Says who? The Dharma orientation tape literally says push the
button.
Speaker 1: Sort of, but… the tape is the lie.
Speaker 2: Okay. Now I'm listening.
```
