# Azure Speech TTS Script Format (SSML)

The Script Writer and Editor agents produce a single **source script** (see
[Source script syntax](#source-script-syntax) below). That same source is
rendered to two targets — Azure SSML (this document) and VibeVoice plain
text ([script_format_vibevoice.md](script_format_vibevoice.md)).

This file covers:

1. The shared source-script syntax the writer/editor produce.
2. How that source is converted into a valid Azure SSML XML document.
3. The native Azure SSML format reference (what the renderer must emit).

Reference:
https://learn.microsoft.com/en-gb/azure/ai-services/speech-service/speech-synthesis-markup-voice

---

## Source script syntax

Plain UTF-8 text. One turn per non-empty line. The writer and editor
both read and emit this format.

### Structural elements

```
[Section Name]               ← full-line bracket = section header (e.g. [Cold Open])
HostName: spoken text…       ← turn line
[Editor's Notes]             ← marks the start of a notes block (stops the script)
- bullet
- bullet
```

- **Section headers** are full-line bracket markers (`[Cold Open]`,
  `[Segment 1: ...]`, `[Outro]`). They are structural only — emitted as
  XML comments in SSML, dropped entirely in VibeVoice.
- **Turn lines** are `HostName: text`. The host-name → voice mapping is
  configured once at render time; the script itself never names a voice.
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
| Sound effect (rare)          | `[sfx:https://…wav]`              | point insertion                               |

Disambiguation: a line that is **only** `[X]` (no spoken text after) is
a section header. A `[X]` cue followed by spoken text on the same line
is an inflection cue. Writers must always put spoken text on the same
line as a cue.

The writer should default to neural-voice styles (e.g. `chat`,
`cheerful`, `serious`, `narration-professional`) unless the producer has
selected an HD voice, in which case the HD style list and
paralinguistics (`[laughter]`, `[sighing]`, `[breathing]`,
`[throat_clearing]`, `[yawning]`, `[coughing]`) become available. Full
lists below.

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

## Source → SSML conversion

The renderer turns each source line into well-formed XML, escaping `&`,
`<`, `>` in spoken text. Default to **Pattern A** (one `<voice>` per
turn, see below) unless the producer has selected the multi-talker HD
voice, in which case use Pattern B.

Conversion rules (apply in order):

1. **Truncate at notes.** Drop everything from the first line matching
   `^\[Editor` onward.
2. **Section headers → comments.** A full-line `[X]` becomes
   `<!-- X -->` placed before the next turn.
3. **Open the document.** Wrap the body in:
   ```xml
   <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
          xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
     …turns…
   </speak>
   ```
4. **Each turn → `<voice>` block.** Resolve `HostName` to its mapped
   voice (e.g. `Ken → en-US-AndrewMultilingualNeural`) and wrap the
   line's text in `<voice name="…">…</voice>`.
5. **Style cues → `<mstts:express-as>`.** A `[style-name]` opens a span
   that runs until the next `[…]` on the same line or end-of-line.
   Each span becomes `<mstts:express-as style="STYLE">…</mstts:express-as>`.
   For HD voices, the renderer may equivalently emit the inline
   `[style-name]` form inside the `<voice>` body.
6. **Paralinguistics** (`[laughter]`, `[sighing]`, etc.) become
   `<mstts:express-as style="laughter">…</mstts:express-as>` (HD voices
   only). On non-HD voices, drop them — they have no neural equivalent.
7. **Pauses → `<break>`.** `(pause)` → `<break strength="medium"/>`.
   `(pause:Nms)` → `<break time="Nms"/>`. Clamp to 0–20000 ms.
8. **Rate / volume → `<prosody>`.** Open a `<prosody>` element on the
   first cue, close it before the next cue of the same family or at
   end-of-line. Map `slow`/`fast` and `soft`/`loud` directly to the
   matching SSML enum values.
9. **Emphasis.** `**word**` → `<emphasis level="strong">word</emphasis>`.
   (Note: SSML emphasis is silently ignored on most voices — only
   `en-US-GuyNeural`, `en-US-DavisNeural`, `en-US-JaneNeural` honor it.
   Emit it anyway; it's harmless on others.)
10. **Language switch.** `[lang:fr-FR]…[/lang]` →
    `<lang xml:lang="fr-FR">…</lang>`. Only valid inside a multilingual
    voice; the renderer should warn if used outside one.
11. **Sound effects.** `[sfx:URL]` → `<audio src="URL">…</audio>` with
    fallback text `(audio)`. URL must be HTTPS.
12. **XML-escape** all spoken text after cue extraction: `&` → `&amp;`,
    `<` → `&lt;`, `>` → `&gt;`. Quote attribute values.

### Mapping example

Input source:

```
Ken: [serious] Well actually, the button isn't doing what they think it's
doing. (pause) That's the whole game.
Maya: [unfriendly] Says who? The Dharma orientation tape literally says
**push the button**.
```

SSML output (with `Ken → en-US-AndrewMultilingualNeural`,
`Maya → en-US-AvaMultilingualNeural`):

```xml
<voice name="en-US-AndrewMultilingualNeural">
  <mstts:express-as style="serious">
    Well actually, the button isn't doing what they think it's doing.
    <break strength="medium"/>
    That's the whole game.
  </mstts:express-as>
</voice>
<voice name="en-US-AvaMultilingualNeural">
  <mstts:express-as style="unfriendly">
    Says who? The Dharma orientation tape literally says
    <emphasis level="strong">push the button</emphasis>.
  </mstts:express-as>
</voice>
```

---

## Native Azure SSML format reference

Azure Speech expects **Speech Synthesis Markup Language (SSML)** — an
XML dialect. Every script is one well-formed XML document rooted at
`<speak>`.

### Document skeleton

Every Azure SSML document **must** begin with this root:

```xml
<speak version="1.0"
       xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts"
       xml:lang="en-US">
  ...
</speak>
```

Required attributes on `<speak>`: `version="1.0"`, `xmlns`, `xml:lang`.
`xmlns:mstts` is required whenever any `mstts:` element is used (which
it almost always is, for styles, dialogs, silences).

Special characters inside text content **must be entity-escaped**: `&` →
`&amp;`, `<` → `&lt;`, `>` → `&gt;`. Attribute values must be quoted.

### Multiple voices: two patterns

#### Pattern A — separate `<voice>` blocks per turn (works with all voices)

Each turn is its own `<voice>` element. Switch voices by closing one and
opening another. This is the universal pattern and what the renderer
defaults to.

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="en-US-AndrewMultilingualNeural">
    Cold open. The hatch in season two —
    everyone remembers the countdown, nobody remembers the lie underneath it.
  </voice>
  <voice name="en-US-AvaMultilingualNeural">
    The lie?
  </voice>
  <voice name="en-US-AndrewMultilingualNeural">
    <mstts:express-as style="serious">
      Well actually, the button isn't doing what they think it's doing.
    </mstts:express-as>
  </voice>
</speak>
```

#### Pattern B — `<mstts:dialog>` multi-talker (HD multi-talker voices only)

For the multi-talker HD voice
`en-US-MultiTalker-Ava-Andrew:DragonHDLatestNeural`, wrap the conversation
in a single `<voice>` and emit each turn as `<mstts:turn speaker="ava">`
/ `<mstts:turn speaker="andrew">`. This produces more natural turn-taking
but locks you to the two speakers baked into that voice.

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="en-US-MultiTalker-Ava-Andrew:DragonHDLatestNeural">
    <mstts:dialog>
      <mstts:turn speaker="ava">Hello, Andrew! How's your day going?</mstts:turn>
      <mstts:turn speaker="andrew">Hey Ava! Exploring AI advancements in
      communication.</mstts:turn>
      <mstts:turn speaker="ava">What kind of projects?</mstts:turn>
    </mstts:dialog>
  </voice>
</speak>
```

Use Pattern A unless you specifically need the multi-talker HD voice.

### Speaking styles, tones, emotion

Two style systems exist depending on the voice you target.

#### Neural voices (non-HD): `<mstts:express-as>`

Wrap a span in `<mstts:express-as style="..." styledegree="..." role="...">`.
The element is per-sentence-level, so use it inside a `<voice>` block,
around the spans you want styled.

```xml
<voice name="en-US-JennyNeural">
  <mstts:express-as style="cheerful" styledegree="1.5">
    That'd be just amazing!
  </mstts:express-as>
  <mstts:express-as style="sad" styledegree="2">
    But it's not going to happen.
  </mstts:express-as>
</voice>
```

`style` (required): one of —
`advertisement_upbeat`, `affectionate`, `angry`, `assistant`, `calm`,
`chat`, `cheerful`, `customerservice`, `depressed`, `disgruntled`,
`documentary-narration`, `embarrassed`, `empathetic`, `envious`,
`excited`, `fearful`, `friendly`, `gentle`, `hopeful`, `lyrical`,
`narration-professional`, `narration-relaxed`, `newscast`,
`newscast-casual`, `newscast-formal`, `poetry-reading`, `sad`,
`serious`, `shouting`, `sports_commentary`, `sports_commentary_excited`,
`whispering`, `terrified`, `unfriendly`.

`styledegree` (optional, `0.01`–`2`, default `1`): intensity multiplier.

`role` (optional): the voice imitates a different age/gender —
`Girl`, `Boy`, `YoungAdultFemale`, `YoungAdultMale`, `OlderAdultFemale`,
`OlderAdultMale`, `SeniorFemale`, `SeniorMale`. Voice name does not
change.

Not every voice supports every style/role. Confirm against
`language-support?tabs=tts#voice-styles-and-roles` before using.

#### HD voices (DragonHD, DragonHD Omni, DragonHD Flash)

HD voices accept the same styles via `<mstts:express-as>` **or** via
inline bracket markers — and the bracket form also works in plain text
fed directly to the voice. Use whichever is more readable.

```xml
<voice name="en-us-Ava:DragonHDLatestNeural">
  <mstts:express-as style="whispering">Don't tell anyone…</mstts:express-as>
  <mstts:express-as style="ecstatic">This is amazing!</mstts:express-as>
</voice>
```

Equivalent inline form:

```xml
<voice name="en-us-Ava:DragonHDLatestNeural">
  [whispering] Don't tell anyone… [ecstatic] This is amazing!
</voice>
```

HD-specific styles (superset of the neural list): `amazed`, `amused`,
`angry`, `annoyed`, `anxious`, `appreciative`, `calm`, `cautious`,
`concerned`, `confident`, `confused`, `curious`, `defeated`,
`defensive`, `defiant`, `determined`, `disappointed`, `disgusted`,
`doubtful`, `ecstatic`, `encouraging`, `excited`, `fast`, `fearful`,
`frustrated`, `happy`, `hesitant`, `hurt`, `impatient`, `impressed`,
`intrigued`, `joking`, `laughing`, `optimistic`, `painful`, `panicked`,
`panting`, `pleading`, `proud`, `quiet`, `reassuring`, `reflective`,
`relieved`, `remorseful`, `resigned`, `sad`, `sarcastic`, `secretive`,
`serious`, `shocked`, `shouting`, `shy`, `skeptical`, `slow`,
`struggling`, `surprised`, `suspicious`, `sympathetic`, `terrified`,
`upset`, `urgent`, `whispering`.

HD paralinguistics (work on all HD voices, all languages): `laughter`,
`coughing`, `throat_clearing`, `breathing`, `sighing`, `yawning`. Use
the same bracket / `express-as` form: `[laughter]` or
`<mstts:express-as style="laughter">`.

#### Roles (neural voices only — not HD)

`role` is a separate axis from `style`. It changes age/gender presentation:

```xml
<voice name="zh-CN-XiaomoNeural">
  <mstts:express-as role="YoungAdultFemale" style="calm">
    "您来的挺快的，怎么过来的？"
  </mstts:express-as>
  <mstts:express-as role="OlderAdultMale" style="calm">
    "刚打车过来的，路上还挺顺畅。"
  </mstts:express-as>
</voice>
```

### Prosody: rate, pitch, volume

`<prosody>` controls per-span delivery. Place inside a `<voice>` element.

```xml
<prosody rate="+30%">spoken faster</prosody>
<prosody pitch="high">higher pitch</prosody>
<prosody volume="+20%">louder</prosody>
<prosody pitch="-2st" rate="slow" volume="soft">quiet, slow, lower</prosody>
```

- `rate`: `0.5`–`2` multiplier, or `±%`, or `x-slow`/`slow`/`medium`/`fast`/`x-fast`.
- `pitch`: `±Hz`, `±st` (semitones), `±%`, or `x-low`/`low`/`medium`/`high`/`x-high`.
  Stay within 0.5–1.5× original.
- `volume`: `0`–`100`, `±` number, `±%`, or
  `silent`/`x-soft`/`soft`/`medium`/`loud`/`x-loud`.
- `range`: same syntax as `pitch`.
- `contour`: `(time%,pitch±)` pairs, e.g. `contour="(0%,+20Hz) (50%,-10Hz)"`.
  Sentence-level only — does not work on single words.

### Emphasis (per-word stress)

```xml
I can help you join your <emphasis level="moderate">meetings</emphasis> fast.
```

`level`: `reduced`, `none`, `moderate` (default), `strong`. Note:
word-level emphasis is only honored on `en-US-GuyNeural`,
`en-US-DavisNeural`, `en-US-JaneNeural`. On other voices it is silently
ignored.

### Pauses and silences

Two mechanisms — `<break>` works anywhere, `<mstts:silence>` only at
sentence or document boundaries.

```xml
Welcome <break time="500ms"/> to text to speech.
Welcome <break strength="strong"/> to text to speech.
```

- `<break time="..."/>`: absolute, `0`–`20000ms`, takes precedence over
  `strength`.
- `<break strength="..."/>`: `x-weak` (250 ms), `weak` (500),
  `medium` (750, default), `strong` (1000), `x-strong` (1250).

Silences applied across a whole `<voice>` block:

```xml
<voice name="en-US-AvaMultilingualNeural">
  <mstts:silence type="Sentenceboundary" value="200ms"/>
  First sentence. Second sentence. Third sentence.
</voice>
```

`type`: `Leading`, `Leading-exact`, `Tailing`, `Tailing-exact`,
`Sentenceboundary`, `Sentenceboundary-exact`, `Comma-exact`,
`Semicolon-exact`, `Enumerationcomma-exact`. The `-exact` variants
replace natural silence instead of adding to it.

### Language switching mid-document

Use `<lang xml:lang="...">` inside a multilingual voice (e.g.
`en-US-AvaMultilingualNeural`, `en-US-AndrewMultilingualNeural`):

```xml
<voice name="en-US-AvaMultilingualNeural">
  <lang xml:lang="en-GB">We look forward to working with you!</lang>
  <lang xml:lang="fr-FR">Nous avons hâte de travailler avec vous!</lang>
</voice>
```

### Embedded audio (sound effects, stings)

```xml
<voice name="en-US-AvaMultilingualNeural">
  <audio src="https://contoso.com/beep.wav">Could not play beep.</audio>
  Thanks for offering your opinion.
</voice>
```

`src` must be HTTPS with a valid TLS cert; `.mp3`, `.wav`, `.opus`,
`.ogg`, `.flac`, or `.wma`. Combined audio + speech ≤ 600 seconds per
request. Fallback text inside the element is spoken if the file fails.

Background bed for the whole document (must be the first child of
`<speak>`, only one allowed):

```xml
<mstts:backgroundaudio src="https://contoso.com/bed.wav"
                       volume="0.7" fadein="3000" fadeout="4000"/>
```

### Full multi-voice podcast example

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">

  <voice name="en-US-AndrewMultilingualNeural">
    <mstts:express-as style="documentary-narration">
      Cold open. The hatch in season two —
      <break time="300ms"/>
      everyone remembers the countdown.
      Nobody remembers the lie underneath it.
    </mstts:express-as>
  </voice>

  <voice name="en-US-AvaMultilingualNeural">
    <mstts:express-as style="chat" styledegree="1.2">
      The lie?
    </mstts:express-as>
  </voice>

  <voice name="en-US-AndrewMultilingualNeural">
    <mstts:express-as style="serious">
      Well actually, the button isn't doing what they think it's doing.
      <break strength="medium"/>
      That's the whole game.
    </mstts:express-as>
  </voice>

  <voice name="en-US-AvaMultilingualNeural">
    <mstts:express-as style="unfriendly" styledegree="0.7">
      Says who? The Dharma orientation tape literally says
      <emphasis level="strong">push the button</emphasis>.
    </mstts:express-as>
  </voice>

  <voice name="en-US-AndrewMultilingualNeural">
    <prosody rate="-10%">Sort of, but…</prosody>
    <break time="400ms"/>
    the tape is the lie.
  </voice>

</speak>
```

### Renderer rules

When rendering source script to SSML:

1. Wrap the entire output in a single `<speak>` element with the required
   namespaces above. Output **valid XML** — escape `&`, `<`, `>` in text.
2. Default to Pattern A (one `<voice>` per turn) unless the producer has
   specified the multi-talker HD voice.
3. Resolve host names to voices via the configured mapping (e.g.
   `Ken → en-US-AndrewMultilingualNeural`,
   `Maya → en-US-AvaMultilingualNeural`) and use the mapping
   consistently across the whole episode.
4. Reach for `<mstts:express-as style="...">` rather than dropping into
   `<prosody>` first — styles are more natural-sounding than manual
   pitch/rate tweaks. Use `<prosody>` only when the source provides
   `(rate:…)` or `(volume:…)` cues.
5. Emit `<break time="...">` for explicit `(pause)` cues; let
   punctuation handle the rest.
6. Do not invent style names. If the source uses an unknown `[style]`,
   either fall back to neutral (drop the wrapper) or pass through as a
   bracket marker for HD voices — but never emit an unknown `style`
   attribute on a neural voice.
7. Keep individual `<voice>` blocks short (one to a few sentences). The
   service handles cross-block transitions cleanly.
```
