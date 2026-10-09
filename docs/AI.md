# Public AI providers (Grok / Gemini / Claude)

CreatorForge can use public AI services to help with words: captions,
titles, hashtags, content ideas, polishing her drafts, and suggesting
chat replies. This is **separate** from her personal AI *video* model --
these are general chat AIs, used like a writing assistant.

## The honest rules

- **Her keys, her money.** Grok (xAI), Gemini (Google), and Claude
  (Anthropic) are paid services. She creates the API key in each
  provider's dashboard and pastes it into `forge.yaml` (or sets
  `XAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` as environment
  variables, which is safer -- keys never sit in a file that way).
- **No key = no fake answers.** Every command refuses with setup
  instructions instead of inventing output.
- **Everything is a draft.** Captions get printed for her to copy;
  `ai reply-assist` can drop its suggestion straight into the approval
  queue. Nothing here posts, sends, or publishes anything, ever.
- **Model names change.** Providers rename models regularly; the
  defaults live in `forge.yaml` under `ai.models` -- if a call 404s,
  check the provider's docs for the current name and update it.

## Commands

| Command | What it does |
|---|---|
| `forge ai providers` | Which providers have keys configured |
| `forge ai ask --prompt "..."` | Freeform question |
| `forge ai caption --topic "..."` | Social captions |
| `forge ai titles --topic "..."` | Video title ideas |
| `forge ai hashtags --topic "..."` | Hashtag suggestions |
| `forge ai ideas --niche "..."` | Video content ideas |
| `forge ai scene-ideas --vibe "..."` | Filmable AI-video scene concepts |
| `forge ai polish --text "..."` | Rewrite her draft punchier |
| `forge ai reply-assist --incoming "..."` | Two reply options for a fan DM (add `--platform` + `--sender` to queue it for approval) |
| `forge ai promo --item "..." --price "..."` | Promo lines for a menu item |

Add `--provider gemini` (or `claude`) to any command to switch backends;
otherwise `ai.default_provider` in `forge.yaml` is used.

## Where the AI plugs in

- **Tube uploads:** `forge tube metadata` writes the structured
  title/description/tags; run the description through
  `forge ai polish` for extra punch before pasting.
- **Chat:** `ai reply-assist` drafts into the same approval queue as
  everything else -- same human review, same rules.
- **Content planning:** `ai ideas` + `ai scene-ideas` feed the scene
  director and the content-ideas module.
