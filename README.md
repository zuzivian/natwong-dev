# PRD: natwong.dev — Personal Portfolio Site
**Type:** Retrospective (written post-launch, documenting as-built decisions)
**Status:** v1 shipped and live
**Author:** Nat Wong

---

## Problem Statement

Heading into Stanford GSB recruiting, I needed a personal portfolio site that gave recruiters and networking contacts a single, memorable place to understand who I am beyond a resume line — specifically, the throughline connecting a background in air defense systems, engineering, and now business school. My previous site (GitHub Pages) was outdated and didn't reflect my current positioning or narrative. Without a credible personal site, I was relying entirely on LinkedIn's generic template to make a first impression, which does nothing to differentiate me in a PM candidate pool where most applicants share a similar CS-then-consulting-or-eng profile.

## Goals

1. **Ship a live, real MVP within a single focused session** — validated: site was scoped, built, and deployed inside a time-boxed window.
2. **Establish a durable personal domain and brand** (natwong.dev) that will outlast this recruiting cycle — validated: domain purchased, deployed, DNS attached.
3. **Differentiate the narrative** from a generic "aspiring PM" story by leading with a genuinely uncommon credential (RSAF officer background) rather than burying it — validated: "systems thinker across domains" framing adopted as the organizing narrative.
4. **Produce something in-house I built myself**, not a template, to serve as an early entry in a broader portfolio-building strategy. — validated: custom-built single-page site with an original visual system (no template).
5. **Set up a deploy pipeline that survives beyond this session** — validated: GitHub repo → Vercel auto-deploy on push, requiring no ongoing manual intervention.

## Non-Goals (v1)

- **Blog / writing section** — deferred. No content plan yet; adding an empty section would signal neglect rather than depth. Revisit once there's actual writing to publish.
- **Case studies / project write-ups** — deferred, intentionally. Build-log section shipped as an explicit placeholder ("first entries in progress") rather than faked content, since the underlying build projects don't exist yet.
- **Custom photography / headshot** — out of scope for v1. The visual identity relies on the radar/schematic motif rather than personal photography, which sidesteps this dependency entirely.
- **Multi-page architecture** — explicitly deferred in favor of a single scrollable page for v1, per initial scoping decision. Revisit if the blog or case-study sections mature enough to need dedicated pages.
- **Open Graph / social share metadata** — flagged post-launch as a gap, not yet fixed. Low effort, deferred only due to time constraints in the original session.
- **Favicon** — same as above: flagged, trivial, not yet done.

## User Stories

- As a **recruiter or networking contact** who just met me, I want to quickly understand what makes my background distinctive, so that I remember me after a short conversation.
- As a **GSB classmate or alum**, I want to see a credible, professional personal site, so that I trust the seriousness of my candidacy for PM roles.
- As **me**, I want a domain and site I own outright (not a LinkedIn-hosted profile), so that my personal brand isn't dependent on a third-party platform's design decisions.
- As **me**, I want the deploy process to require zero ongoing manual work, so that updating the site later doesn't compete with other priorities.

## Requirements (as-built)

### Must-Have (P0) — shipped
- [x] Custom domain (natwong.dev) live and resolving
- [x] Single-page layout: hero, four-domain narrative grid, bio, timeline, contact footer
- [x] Distinct visual identity tied to actual subject matter (radar/schematic motif referencing air-defense background), not a generic AI-design default
- [x] Fully spelled-out copy — no unexplained abbreviations (RSAF, GSB, BS/MS, PSC, SAF all expanded), given the site's audience includes an international/US recruiting readership unfamiliar with Singapore-specific institutional shorthand
- [x] Accurate representation of the Public Service Commission Scholarship / Singapore Armed Forces Scholarship relationship (PSC scholarship as prerequisite, not identical to SAF Scholarship)
- [x] Mobile-responsive layout
- [x] Accessibility floor: keyboard focus states, `prefers-reduced-motion` respected (radar sweep and aircraft tracks disable cleanly)
- [x] Auto-deploy pipeline: GitHub repo → Vercel, redeploys on every push

### Nice-to-Have (P1) — shipped, iterated post-launch
- [x] Animated radar sweep in hero background
- [x] Simulated aircraft "contacts" — refined twice post-initial-launch based on direct feedback: first pass used smooth orbiting arcs; revised to straight-line flight paths with sweep-gated position updates (contacts only refresh when the sweep beam passes over them), matching how real rotating-antenna radar actually behaves, with intentional CRT-style jitter for a rugged/retro read rather than a smooth animation
- [x] Visual legibility pass — increased contact opacity, size, and glow, and added two additional simultaneous contacts, after initial version read as too faint against the background

### Future Considerations (P2) — explicitly not built, but designed not to block
- [ ] Blog/writing section — page structure should accommodate this without a full rebuild
- [ ] Case studies for build projects, once they exist
- [ ] Open Graph tags for social sharing
- [ ] Favicon

## Success Metrics

**Leading indicators** (immediate, self-assessable):
- Site live and resolving on custom domain — met
- Zero broken content or copy errors on live deploy — verified via direct fetch post-launch
- Deploy pipeline requires no manual redeploy step going forward — met (GitHub → Vercel)

**Lagging indicators** (only measurable over time, not yet evaluated):
- Whether the site becomes a genuine differentiator in networking conversations (anecdotal — track whether contacts mention it unprompted)
- Whether it gets referenced positively during actual PM recruiting conversations

*Note: this is a personal portfolio, not a product with users at scale — success here is qualitative and self-assessed rather than instrumented with analytics. No analytics/tracking has been added, deliberately, to avoid over-engineering v1.*

## Open Questions

- **Design/content**: Should the build-log placeholder be replaced with real entries as soon as the first project ships, or batched until a few are ready? *(owner: Nat)*
- **Content**: Does the "systems thinker across domains" narrative need updating once a specific PM functional lane is decided, or does it stay evergreen across that decision? *(owner: Nat)*
- **Technical**: At what point does the single-file HTML structure become a liability (e.g., once a blog is added)? Worth migrating to a proper framework (Next.js) then, likely via Claude Code rather than single-file iteration. *(owner: Nat, technical)*

## Timeline Considerations

- **Built and shipped** in a single focused session, scoped explicitly to fit inside a limited time window rather than left open-ended
- **Dependency**: build-log/case-study content depends on future build projects, which are lower priority than other near-term commitments
- **No hard external deadline** for this project — it was time-boxed by choice, not by an imposed cutoff, to avoid open-ended time investment
