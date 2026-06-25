# Voice Samples Guide

Audio samples live in subdirectories alongside this file. Listen before assigning a voice to a host — the right match makes dialogue feel like a real person.

---

## VibeVoice 7B

VibeVoice has **no style tags**. Delivery is shaped entirely by punctuation, word choice, and sentence rhythm. The emotional baseline (warm, dry, energetic) comes from the reference voice itself. Samples are single `.wav` files — one per voice.

> **How to listen:** Open any `.wav` in `voice-samples/vibe-voice/`.

| Voice | Gender | Accent | Tone & Texture | Best For | Sample File |
|-------|--------|--------|----------------|----------|-------------|
| Alice | Female | English (US) | Warm, conversational, clear. Natural pacing and approachable delivery. | Curious hosts, friendly interviewers, accessible explainers | `vibe-voice/en-Alice_woman.wav` |
| Carter | Male | English (US) | Authoritative, confident, measured. Carries weight without being stiff. | Expert analysts, lead hosts, authoritative commentators | `vibe-voice/en-Carter_man.wav` |
| Frank | Male | English (US) | Casual, laid-back, relatable. Feels like a knowledgeable friend explaining something. | Skeptics, everyman co-hosts, comedic relief, devil's advocates | `vibe-voice/en-Frank_man.wav` |
| Maya | Female | English (US) | Expressive, energetic, dynamic. Wide emotional range and forward momentum. | Enthusiastic experts, high-energy hosts, passionate practitioners | `vibe-voice/en-Maya_woman.wav` |
| Mary | Female | English (US) | Rich, narrative tone with a subtle ambient texture (light background music baked in). | Storytellers, reflective hosts, documentary-style narration | `vibe-voice/en-Mary_woman_bgm.wav` |
| Samuel | Male | Indian English | Deep, measured, thoughtful. Carries gravitas naturally. | Senior experts, philosophical perspectives, calm counterpoints | `vibe-voice/in-Samuel_man.wav` |

**Note on style in VibeVoice:** There are no style cues in the rendered script. To shape delivery, write the way you want it to sound — use `...` for hesitation, `—` for a beat, `!` for energy, short sentences for urgency, longer ones for calm.

---

## MAI-2 (Azure MAI Voice 2)

MAI-2 voices support **speaking styles** via SSML `<mstts:express-as style="...">`. The script formatter applies styles automatically based on the emotional register of each line.

> **How to listen:** Each voice has a subdirectory in `voice-samples/mai-2/<VoiceName>/` with one `.mp3` per style (e.g. `happy.mp3`, `regretful.mp3`). Run `generate_mai2_samples.py` first if the directory is empty.

**SSML format:**
```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="en-US-Ethan:MAI-Voice-2">
    <mstts:express-as style="happy">I can't wait to dig into this topic with you!</mstts:express-as>
  </voice>
</speak>
```

| Voice ID | Gender | Accent | Tone & Texture | Best For | Supported Styles | Sample Dir |
|----------|--------|--------|----------------|----------|------------------|------------|
| `en-AU-Isla:MAI-Voice-2` | Female | Australian English | Full emotional range with a natural Australian accent. | Storytellers, opinionated hosts, shows with international flavour | angry, confused, determined, disgusted, embarrassed, excited, fearful, happy, hopeful, jealous, joyful, regretful, relieved, sad, shouting, softvoice, surprised, whispering | `mai-2/Isla/` |
| `en-US-Ethan:MAI-Voice-2` | Male | English (US) | Conversational, approachable US male. Full emotional range. | Everyman perspective, skeptics, casual co-hosts, curious questioners | angry, confused, determined, disgusted, embarrassed, excited, fearful, happy, hopeful, jealous, joyful, regretful, relieved, sad, shouting, softvoice, surprised, whispering | `mai-2/Ethan/` |
| `en-US-Grant:MAI-Voice-2` | Male | English (US) | Neutral, clear delivery. No expression styles — consistent, uncoloured tone. | Steady narrators, hosts needing clean neutral delivery | *(none — neutral only)* | `mai-2/Grant/` |
| `en-US-Harper:MAI-Voice-2` | Female | English (US) | Warm, determined US female. Strong emotional range. | Lead hosts, warm interviewers, determined storytellers | angry, confused, determined, embarrassed, excited, happy, hopeful, joyful, regretful, relieved, sad, shouting, softvoice, whispering | `mai-2/Harper/` |
| `en-US-Iris:MAI-Voice-2` | Female | English (US) | Clear, natural US female delivery. No expression styles. | Steady narrators, hosts needing clean neutral delivery | *(none — neutral only)* | `mai-2/Iris/` |
| `en-US-Jasper:MAI-Voice-2` | Male | English (US) | Clear, composed US male delivery. No expression styles. | Steady narrators, hosts needing clean neutral delivery | *(none — neutral only)* | `mai-2/Jasper/` |
| `en-US-Olivia:MAI-Voice-2` | Female | English (US) | Expressive, dynamic US female. Full emotional range including subtler emotions. | Passionate experts, opinionated hosts, dramatic or high-energy moments | angry, confused, determined, disgusted, embarrassed, excited, fearful, happy, hopeful, jealous, joyful, regretful, relieved, sad, shouting, softvoice, surprised, whispering | `mai-2/Olivia/` |

---

## Choosing a Voice

Match voice character to host personality, not just gender. Some quick heuristics:

- **Expert who knows everything** → Carter (VibeVoice), Ethan or Jasper (MAI-2)
- **Curious questioner who drives the narrative** → Alice (VibeVoice), Harper or Iris (MAI-2)
- **Enthusiastic practitioner** → Maya (VibeVoice), Olivia or Ethan (MAI-2)
- **Skeptic or devil's advocate** → Frank (VibeVoice), Ethan (MAI-2)
- **Storyteller / dramatic narrator** → Mary (VibeVoice), Isla or Olivia (MAI-2)
- **Steady, neutral host** → Carter (VibeVoice), Grant, Iris, or Jasper (MAI-2)
- **Warm, determined lead** → Alice (VibeVoice), Harper (MAI-2)

For shows with two hosts, pick voices with contrast — e.g. one warm/casual (Frank, Alice / Harper, Ethan) + one authoritative/precise (Carter / Grant, Jasper).
