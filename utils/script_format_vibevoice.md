# VibeVoice Script Format (1.5B / 7B)

VibeVoice is a plain-text TTS model. There is **no markup language** — speaker
turns are encoded as line-prefixed labels and the model infers emotion, pace,
and emphasis from natural punctuation and word choice.

## File format

- A single UTF-8 `.txt` file.
- One turn per line. Each line begins with a speaker label, then a colon, then
  the spoken text.
- Lines are separated by a single newline. Do **not** add blank lines between
  turns.
- Up to **4 distinct speakers** per file (1.5B and 7B). Total audio length up
  to ~90 minutes.

## Speaker labels

Use `Speaker 1:`, `Speaker 2:`, `Speaker 3:`, `Speaker 4:` — numbered, 1-indexed,
exact casing, single space after the word "Speaker", colon then a single space
before the text.

```
Speaker 1: Hey, remember "See You Again"?
Speaker 2: Yeah… from Furious 7, right? That song always hits deep.
Speaker 1: Let me try to sing a part of it for you.
```

The mapping from `Speaker N` to a real voice is supplied at inference time via
the `--speaker_names` CLI flag (e.g. `--speaker_names Alice Frank` →
`Speaker 1=Alice`, `Speaker 2=Frank`). The script itself never names voices.

### Pre-trained voices (for `--speaker_names`)

`Alice` (en, woman), `Carter` (en, man), `Frank` (en, man), `Maya` (en, woman),
`Mary` (en, woman, includes BGM), `Samuel` (in, man), `Anchen` (zh, man, BGM),
`Bowen` (zh, man), `Xinran` (zh, woman).

Custom voices: pass any name; supply a matching reference audio sample for
voice cloning.

## Multi-turn / multi-voice

Alternate speakers freely across consecutive lines. The model handles
turn-taking and prosody between speakers natively — do not add transition cues.

```
Speaker 1: So, the cold open. Three lines, big hook.
Speaker 2: Says who? Two is plenty if the hook lands.
Speaker 1: Counter-argument: pacing.
Speaker 2: Fair.
```

If a single speaker has a long monologue and the rendered voice speeds up,
**chunk it across multiple consecutive lines with the same label** rather than
one giant line:

```
Speaker 1: Here's the thing about the hatch.
Speaker 1: It's not really about the button at all.
Speaker 1: The button is a test of faith, dressed up as a science experiment.
```

## Speaking styles, tones, emotion

VibeVoice has **no style tags, no SSML, no bracketed cues**. It conditions on:

1. **Punctuation** — `?` raises pitch, `!` adds energy, `…` and `,` add pauses,
   `—` adds a beat, `.` lands a sentence.
2. **Word choice and content** — write the way you want it to sound. "I
   whispered" or "she screamed" inside narration is ignored; instead, write
   short clipped sentences for tension or long flowing ones for calm.
3. **Reference voice** — emotional baseline (warm, dry, energetic) comes from
   the speaker's reference audio sample, not from the script.

Do **not** write tags like `[whispering]`, `[laughs]`, `<emphasis>`, or stage
directions in parentheses. They will be read aloud literally.

To shape delivery, use only:

- Ellipses for hesitation: `Well… I'm not sure.`
- Em dashes for interruption or beat: `It was — and this is the wild part —
  exactly the same hatch.`
- Repetition for emphasis: `No. No, no, no.`
- Short sentences for urgency, longer ones for reflection.
- Onomatopoeia or written-out laughter when a sound is wanted: `Ha. Right.`

## Example: 2-speaker podcast turn

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

## Output rules for the script writer

When generating a VibeVoice script:

1. Start every line with `Speaker N:` — no other prefixes, no segment headers,
   no bracketed scene labels.
2. Map host names to speaker numbers consistently across the whole episode
   (e.g. Ken=Speaker 1, Maya=Speaker 2). Output the mapping once at the top of
   the file as a `# comment` line that the inference script will ignore, or
   record it separately — never inline in a turn.
3. Write the actual dialogue you want spoken. Read each line aloud; if it
   sounds wrong as plain English, the model will say it wrong.
4. Keep each line under ~50 words. Split long monologues across multiple
   same-speaker lines.
5. No SSML. No bracketed cues. No markdown.
