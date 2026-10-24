# Workflow

Status flow: draft -> reviewed -> pending_review -> approved or changes_requested

| Status | Meaning | Who moves it on |
|---|---|---|
| draft | Content saved, AI review not run yet (only seen if the review failed, e.g. no rule book) | Creator runs the review |
| reviewed | AI review done. The creator accepts or rejects each suggested fix | Creator sends it once every issue is decided |
| pending_review | Waiting in the reviewer's queue. Locked: the creator cannot edit it | Reviewer decides |
| approved | Reviewer approved. The final text (original + accepted fixes) is stored | End |
| changes_requested | Reviewer wrote a comment asking for changes | Creator clicks "Apply accepted fixes and review again" -> back to `reviewed` |

## Step by step

1. Brand Manager uploads the rule book (Rule Book page). Only one rule book is active at a time.
2. Creator adds content (New Content page: paste text or upload .txt / .pdf / .docx). The review starts automatically.
3. Four checks run:
   - Terminology (plain Python): restricted words from the rule book, e.g. "users" -> "customers".
   - Facts (plain Python): numbers compared with the rule book, e.g. "50,000 users" vs 14,000 customers; wrong founding year.
   - Claims (built-in rules + Gemini): rankings like "#1" or "best", guaranteed results, unsourced statistics.
   - Tone (Gemini, or built-in hype-phrase rules if there is no key): exclamation spam, over-excited wording.
4. Creator sees the highlighted text, a score and a list of issues; accepts or rejects each fix.
5. Creator sends it to the reviewer. The reviewer sees original vs revised text and which fixes the creator rejected.
6. Reviewer approves, or requests changes with a comment. The creator can fix and review again.

If two checks flag the same words, only one finding is kept (fact > claim > terminology > tone) so accepting fixes can never corrupt the text.
