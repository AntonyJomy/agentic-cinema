# Specialist Agent card videos

Four placeholder paths are wired up in `Services.jsx` and rendered by
`.service-visual-video` in `Services.css`. None of the actual MP4 files
exist yet — drop a matching file at each path below and it starts playing
immediately, no code changes needed. Until then, `.service-visual`'s
existing amber gradient background shows through as a graceful fallback.

Shared requirements for all four:
- MP4 / H.264, no audio track needed (the `<video>` is muted).
- 1080p is enough — these render at well under full width inside a card.
- Loops seamlessly (no visible cut/jump at the loop point) — a few
  seconds of slow, minimal camera movement loops far more convincingly
  than a static locked-off shot cut hard at both ends.
- No visible text, captions, watermarks, or logos anywhere in frame.
- No recognizable faces of real, identifiable people (this is a legal-risk
  product — recognizable people in its own marketing footage would be an
  odd contradiction) if using stock footage of "a person," prefer
  anonymized/silhouette/back-of-frame/out-of-focus framing.
- Source from a license that explicitly permits commercial/public website
  use (e.g. Pexels License, Pixabay License, Mixkit Free License, or CC0).
  Record the source URL + license + clip ID for each file used, either in
  this file or a comment at the top of it, before shipping.

## business-brand.mp4
**Agent 01 — Business & Brand.** Checks named companies/brands/logos
against real-world registrations.
Concept: storefront signage, a logo mounted on a building exterior,
close-up of branded packaging or product detail, a retail shopfront.
Should read as "verifying whether a real business/brand exists" — avoid
generic office/meeting-room stock footage.

## character-identity.mp4
**Agent 02 — Character & Identity.** Checks whether a fictional character
could be mistaken for a real, identifiable person.
Concept: editorial/investigative human footage — a profile shot, someone
entering a building, an observational close-up (anonymized/out of focus
where a face would otherwise be clearly identifiable). Should feel
documentary, not a corporate headshot or lifestyle-brand smiling shot.

## music-literary.mp4
**Agent 03 — Music & Literary.** Traces song lyrics, book quotes, and
cultural references to their rights holder.
Concept: a vinyl record/turntable, a hand over sheet music or a manuscript
page, a writing desk with books. Atmospheric and conceptual — do not use
footage of an actual recognizable song performance or music video.

## privacy-location.mp4
**Agent 04 — Privacy & Location.** Verifies whether a shown street
address, phone number, or license plate resolves to a real location.
Concept: a street number on a door, a mailbox, a license plate on a
parked car, a phone screen showing a number (no real, resolvable address/
plate/number — use a fabricated or heavily obscured one). Quiet and
observational, matching the copy's "quiet but real" framing — not
dramatic or thriller-toned.
