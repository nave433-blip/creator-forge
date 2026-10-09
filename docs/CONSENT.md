# Consent

## Why this gate exists

CreatorForge can train an AI model on a real person's face and body and
generate realistic videos of her. That is powerful and dangerous in the
wrong hands: the same pipeline could be pointed at anyone's photos.

So the video pipeline has a **hard consent gate**: it will not train,
configure, or generate anything unless a signed consent record from the
person herself validates. This is enforced in code
(`forge/identity/pack.py` + `forge/video/pipeline.py`), not just in docs.
No valid consent pack = generation is refused, every time.

**Rules:**
- Consent must come from the creator herself -- the person whose likeness
  is used. Not a friend, manager, or partner signing on her behalf.
- She must be an adult (18+).
- She can revoke consent any time: delete the identity pack and the
  trained model files. CreatorForge has no cloud copy of either.

## Consent form template

Copy this into a text file, have her fill it in and sign it (a typed
name + date counts as the signature here; keep the file with the pack),
then run:

```bash
forge identity create --statement-file signed-consent.txt --out identity-pack.yaml
```

---

> **CONSENT FOR AI LIKENESS USE -- CreatorForge**
>
> I, _________________________ (full legal name), confirm that:
>
> 1. I am 18 years of age or older.
> 2. I am the person whose photos and videos ("my content") will be used.
> 3. I consent to my content being used to train an AI likeness model of
>    me, and to that model generating AI videos/images of me.
> 4. Scope of use (what the AI content may be used for):
>    ___________________________________________________________
>    (example: "posting on my own OnlyFans, Snapchat, Reddit, and
>    TikTok accounts")
> 5. I understand I can revoke this consent at any time by asking for
>    the identity pack and trained model files to be deleted.
> 6. I understand the generated content is AI-generated and I am
>    responsible for labeling it as such where a platform requires it.
>
> Signed: _________________________   Date: ____________ (YYYY-MM-DD)

---

## Technical notes

- The identity pack stores a SHA-256 checksum of the exact statement
  text. If anyone edits the pack or statement afterwards, validation
  fails and the pipeline refuses to run.
- Keep `identity-pack.yaml` and the signed statement somewhere safe and
  private -- they identify a real person. Do not commit them to a public
  repo.
- To revoke: delete the pack file and any trained `.safetensors` model
  files. Without the pack, nothing in CreatorForge will generate her
  likeness again.
