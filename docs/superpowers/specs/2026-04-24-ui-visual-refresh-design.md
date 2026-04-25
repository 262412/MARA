# UI Visual Refresh Design

Date: 2026-04-24
Status: Approved for implementation
Scope: Refresh the Slides/Kotaemon Gradio application styling, color system, and UI surface treatment without changing the product workflow or information architecture.

## Summary

Slides is a local document QA and RAG workbench with chat, document preview, citation review, file management, settings, and knowledge graph exploration. The UI should feel like a precise research workbench rather than a marketing site or a decorative AI demo.

The approved direction is:

- Use a "precise research workbench" style as the default light theme.
- Keep the existing dark, graph-oriented energy as inspiration for dark mode.
- Borrow a warmer reading-library feel for document preview and citation surfaces.

The result should be professional, readable for long sessions, and visually varied enough to avoid a single-hue blue-green product.

## Goals

- Improve perceived clarity and polish of the Gradio Web UI.
- Make the default theme lighter, calmer, and better suited to reading and citation review.
- Preserve dark mode as a focused knowledge-graph and expert-workflow variant.
- Use warm paper-like surfaces only where they help reading, especially document preview and evidence/citation-style cards.
- Keep the implementation scoped to theme tokens and CSS.

## Non-Goals

- Replacing Gradio or restructuring the app layout.
- Changing chat, indexing, model routing, or knowledge graph behavior.
- Adding new runtime dependencies.
- Creating a landing page or marketing-style hero screen.

## Visual Direction

### Default Light Theme

The default theme uses a neutral, research-tool palette:

- ink text: deep slate
- main accent: teal for primary action and selected state
- supporting accent: blue for links, citations, and navigational affordances
- surfaces: near-white and cool gray
- reading surfaces: warm paper tint used sparingly

The UI should look quiet and operational. Tabs, panels, chat areas, file tables, and settings should be easy to scan and should not rely on heavy gradients.

### Dark Theme

Dark mode keeps a graph-lab personality without overusing glow effects:

- background: deep navy/slate
- panel surface: slightly lifted blue-slate
- primary accent: mint/teal
- secondary accent: cyan/blue
- borders: restrained slate contrast

Dark mode should be suitable for graph exploration and power users, but not become the only visual identity.

### Reading And Citation Surfaces

Document preview, citation hints, and evidence cards can use a warmer surface:

- paper background tint
- subtle neutral border
- restrained shadow
- no oversized decorative cards

This gives document-heavy workflows a more comfortable reading feel while keeping the rest of the app crisp and technical.

## Implementation Strategy

The implementation stays in the existing styling layer:

- `libs/ktem/ktem/assets/theme.py` defines Gradio theme tokens and color hues.
- `libs/ktem/ktem/assets/css/main.css` defines app-level CSS variables and custom component styling.
- `libs/ktem/ktem_tests/test_assets_theme.py` verifies the style contract at the token and CSS-variable level.

The CSS should centralize app color variables near `:root` and avoid scattering unrelated hard-coded colors for the refreshed surfaces.

## Testing Strategy

Automated tests should verify:

- the app theme keeps teal as primary and blue as secondary hue
- the custom CSS exposes light, dark, and reading-surface variables
- key surfaces use the reading variable rather than unrelated hard-coded beige or old slate-only values
- the CSS keeps knowledge graph styling present

Manual verification should include:

- launching the Gradio app
- checking the main tab, chat/preview split, knowledge graph area, settings/help tabs, and dark mode if available
- confirming text remains readable and controls do not overlap
