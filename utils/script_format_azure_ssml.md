# Azure Speech TTS Script Format (SSML)

Azure Speech expects **Speech Synthesis Markup Language (SSML)** — an XML
dialect. Every script is one well-formed XML document rooted at `<speak>`.

Reference:
https://learn.microsoft.com/en-gb/azure/ai-services/speech-service/speech-synthesis-markup-voice

## Document skeleton

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
`xmlns:mstts` is required whenever any `mstts:` element is used (which it
almost always is, for styles, dialogs, silences).

Special characters inside text content **must be entity-escaped**: `&` → `&amp;`,
`<` → `&lt;`, `>` → `&gt;`. Attribute values must be quoted.

## Multiple voices: two patterns

### Pattern A — separate `<voice>` blocks per turn (works with all voices)

Each turn is its own `<voice>` element. Switch voices by closing one and
opening another. This is the universal pattern and what you should default to.

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

### Pattern B — `<mstts:dialog>` multi-talker (HD multi-talker voices only)

For the multi-talker HD voice
`en-US-MultiTalker-Ava-Andrew:DragonHDLatestNeural`, wrap the conversation in
a single `<voice>` and emit each turn as `<mstts:turn speaker="ava">` /
`<mstts:turn speaker="andrew">`. This produces more natural turn-taking but
locks you to the two speakers baked into that voice.

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

## Speaking styles, tones, emotion

Two style systems exist depending on the voice you target.

### Neural voices (non-HD): `<mstts:express-as>`

Wrap a span in `<mstts:express-as style="..." styledegree="..." role="...">`.
The element is per-sentence-level, so use it inside a `<voice>` block, around
the spans you want styled.

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
`advertisement_upbeat`, `affectionate`, `angry`, `assistant`, `calm`, `chat`,
`cheerful`, `customerservice`, `depressed`, `disgruntled`,
`documentary-narration`, `embarrassed`, `empathetic`, `envious`, `excited`,
`fearful`, `friendly`, `gentle`, `hopeful`, `lyrical`, `narration-professional`,
`narration-relaxed`, `newscast`, `newscast-casual`, `newscast-formal`,
`poetry-reading`, `sad`, `serious`, `shouting`, `sports_commentary`,
`sports_commentary_excited`, `whispering`, `terrified`, `unfriendly`.

`styledegree` (optional, `0.01`–`2`, default `1`): intensity multiplier.

`role` (optional): the voice imitates a different age/gender —
`Girl`, `Boy`, `YoungAdultFemale`, `YoungAdultMale`, `OlderAdultFemale`,
`OlderAdultMale`, `SeniorFemale`, `SeniorMale`. Voice name does not change.

Not every voice supports every style/role. Confirm against
`language-support?tabs=tts#voice-styles-and-roles` before using.

### HD voices (DragonHD, DragonHD Omni, DragonHD Flash)

HD voices accept the same styles via `<mstts:express-as>` **or** via inline
bracket markers — and the bracket form also works in plain text fed directly
to the voice. Use whichever is more readable.

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

HD-specific styles (superset of the neural list): `amazed`, `amused`, `angry`,
`annoyed`, `anxious`, `appreciative`, `calm`, `cautious`, `concerned`,
`confident`, `confused`, `curious`, `defeated`, `defensive`, `defiant`,
`determined`, `disappointed`, `disgusted`, `doubtful`, `ecstatic`,
`encouraging`, `excited`, `fast`, `fearful`, `frustrated`, `happy`, `hesitant`,
`hurt`, `impatient`, `impressed`, `intrigued`, `joking`, `laughing`,
`optimistic`, `painful`, `panicked`, `panting`, `pleading`, `proud`, `quiet`,
`reassuring`, `reflective`, `relieved`, `remorseful`, `resigned`, `sad`,
`sarcastic`, `secretive`, `serious`, `shocked`, `shouting`, `shy`,
`skeptical`, `slow`, `struggling`, `surprised`, `suspicious`, `sympathetic`,
`terrified`, `upset`, `urgent`, `whispering`.

HD paralinguistics (work on all HD voices, all languages): `laughter`,
`coughing`, `throat_clearing`, `breathing`, `sighing`, `yawning`. Use the same
bracket / `express-as` form: `[laughter]` or `<mstts:express-as
style="laughter">`.

### Roles (neural voices only — not HD)

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

## Prosody: rate, pitch, volume

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

## Emphasis (per-word stress)

```xml
I can help you join your <emphasis level="moderate">meetings</emphasis> fast.
```

`level`: `reduced`, `none`, `moderate` (default), `strong`. Note: word-level
emphasis is only honored on `en-US-GuyNeural`, `en-US-DavisNeural`,
`en-US-JaneNeural`. On other voices it is silently ignored.

## Pauses and silences

Two mechanisms — `<break>` works anywhere, `<mstts:silence>` only at sentence
or document boundaries.

```xml
Welcome <break time="500ms"/> to text to speech.
Welcome <break strength="strong"/> to text to speech.
```

- `<break time="..."/>`: absolute, `0`–`20000ms`, takes precedence over `strength`.
- `<break strength="..."/>`: `x-weak` (250 ms), `weak` (500), `medium` (750,
  default), `strong` (1000), `x-strong` (1250).

Silences applied across a whole `<voice>` block:

```xml
<voice name="en-US-AvaMultilingualNeural">
  <mstts:silence type="Sentenceboundary" value="200ms"/>
  First sentence. Second sentence. Third sentence.
</voice>
```

`type`: `Leading`, `Leading-exact`, `Tailing`, `Tailing-exact`,
`Sentenceboundary`, `Sentenceboundary-exact`, `Comma-exact`, `Semicolon-exact`,
`Enumerationcomma-exact`. The `-exact` variants replace natural silence
instead of adding to it.

## Language switching mid-document

Use `<lang xml:lang="...">` inside a multilingual voice (e.g.
`en-US-AvaMultilingualNeural`, `en-US-AndrewMultilingualNeural`):

```xml
<voice name="en-US-AvaMultilingualNeural">
  <lang xml:lang="en-GB">We look forward to working with you!</lang>
  <lang xml:lang="fr-FR">Nous avons hâte de travailler avec vous!</lang>
</voice>
```

## Embedded audio (sound effects, stings)

```xml
<voice name="en-US-AvaMultilingualNeural">
  <audio src="https://contoso.com/beep.wav">Could not play beep.</audio>
  Thanks for offering your opinion.
</voice>
```

`src` must be HTTPS with a valid TLS cert; `.mp3`, `.wav`, `.opus`, `.ogg`,
`.flac`, or `.wma`. Combined audio + speech ≤ 600 seconds per request. Fallback
text inside the element is spoken if the file fails.

Background bed for the whole document (must be the first child of `<speak>`,
only one allowed):

```xml
<mstts:backgroundaudio src="https://contoso.com/bed.wav"
                       volume="0.7" fadein="3000" fadeout="4000"/>
```

## Full multi-voice podcast example

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

## Output rules for the script writer

When generating an Azure SSML script:

1. Wrap the entire output in a single `<speak>` element with the required
   namespaces above. Output **valid XML** — escape `&`, `<`, `>` in text.
2. Default to Pattern A (one `<voice>` per turn) unless the producer has
   specified the multi-talker HD voice.
3. Choose voices once at the top (e.g. Ken → `en-US-AndrewMultilingualNeural`,
   Maya → `en-US-AvaMultilingualNeural`) and use them consistently.
4. Reach for `<mstts:express-as style="...">` rather than dropping into
   `<prosody>` first — styles are more natural-sounding than manual pitch/rate
   tweaks. Use `<prosody>` for fine-grained adjustments only.
5. Use `<break time="...">` for deliberate beats; let punctuation handle the
   rest.
6. Do not invent style names. Stick to the table above. An unknown `style`
   silently falls back to neutral on neural voices, or is read literally on HD
   voices when used as a `[bracket]` marker.
7. Keep individual `<voice>` blocks short (one to a few sentences). The
   service handles cross-block transitions cleanly.
