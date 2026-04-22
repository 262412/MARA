# Knowledge Graph Viewer Redesign

Date: 2026-04-22
Status: Drafted and approved for planning review
Scope: Replace the inline knowledge graph panel with a NotebookLM-style preview card and fullscreen graph viewer while preserving existing node-to-question behavior.

## Summary

The current knowledge graph renders directly inside the `Knowledge Graph` panel. This works for small trees, but large graphs become difficult to read because the panel is constrained and does not provide a dedicated fullscreen exploration experience. The new design replaces the inline graph with a clickable preview card. Opening that card launches a fullscreen overlay viewer that supports drag-to-pan, mouse-wheel zoom, explicit zoom controls, and reset-to-fit behavior.

The redesign intentionally preserves the existing knowledge graph generation pipeline, schema v2 structure, split-map behavior, and node click prompt-filling flow. The primary change is presentation and interaction, not graph semantics.

## Goals

- Replace the current always-expanded inline graph with a compact preview card in the `Knowledge Graph` area.
- Open the full graph in a fullscreen overlay instead of showing it inline.
- Support smooth pan and zoom interactions in the fullscreen viewer.
- Preserve current node click behavior:
  - clicking a node writes `graph_context`
  - clicking a node fills the chat input with a suggested question
  - clicking a node does not auto-send the question
- Preserve current single-map and multi-map rendering semantics.
- Reuse project patterns where possible instead of introducing a disconnected UI paradigm.

## Non-Goals

- Rebuilding the knowledge graph as SVG or Canvas.
- Changing knowledge extraction, clustering, split-map decisions, or graph schema contracts.
- Replacing the current question-filling behavior with auto-send or a new chat flow.
- Creating a separate browser tab or route for graph viewing.

## User Experience

### Panel State

The `Knowledge Graph` panel no longer shows the full graph by default. Instead it shows a single preview card that represents the current graph artifact.

The preview card includes:

- graph title
- source count
- generation state
- split-map notice when the graph has been divided into multiple maps
- a clear call to action such as `Open Graph`

If the graph is still generating, the card stays visible but shows a progress-style status. If generation failed or no graph exists, the card presents a failure or empty-state message and keeps the existing refresh affordance nearby.

### Fullscreen Viewer

Clicking the preview card opens a fullscreen overlay that covers the current page. The overlay contains:

- a top bar with title and source count
- a close button
- zoom controls for zoom in, zoom out, reset, and fit-to-screen
- a dedicated graph viewport containing the full rendered graph

The viewer should feel like a focused exploration space, not like a narrow panel stretched larger.

### Interaction Model

Inside the fullscreen viewer:

- pointer drag pans the graph
- mouse wheel zooms in and out
- toolbar controls provide explicit zoom actions
- opening the viewer auto-fits the graph into view
- resetting the view returns the graph to a readable, centered baseline

Node clicks keep their current meaning. A user can still open the large viewer, inspect the graph, click a node, and immediately get the node-specific prompt drafted in the chat input without sending it automatically.

## Recommended Approach

Three implementation approaches were considered:

1. Card preview plus fullscreen overlay plus HTML graph pan/zoom
2. Card preview plus fullscreen overlay with scroll-only navigation
3. Card preview plus fullscreen overlay backed by a rewritten SVG or Canvas renderer

Approach 1 is the approved option. It gives the user the exploration experience they want while keeping the existing HTML-based graph renderer and node click payload wiring intact. It limits risk by treating the graph as an interactive document inside a dedicated viewer instead of replacing the rendering stack.

## Architecture

### Rendering Strategy

The graph renderer continues to produce the same semantic graph HTML for single-map and split-map outputs. The presentation wrapper changes:

- in the chat panel, the knowledge graph area renders a preview card shell
- the fullscreen overlay hosts the real graph viewport
- the overlay reuses the renderer's HTML output rather than generating a second graph format

This keeps the graph artifact contract stable and concentrates work in the renderer wrapper, front-end interactions, and viewer styles.

### Viewer Structure

The fullscreen viewer is made of three layers:

1. Overlay container
2. Viewport element
3. Stage element holding the rendered graph HTML

The viewport is the visible window. The stage is translated and scaled by JavaScript. The graph itself remains normal HTML content inside that stage.

### State Model

The viewer maintains a minimal interaction state:

- `isOpen`
- `scale`
- `translateX`
- `translateY`
- drag state such as pointer origin and whether the current gesture exceeded the click threshold

The knowledge graph data itself remains server-rendered as before. The viewer state is purely client-side and ephemeral.

## Components

### 1. Preview Card

The preview card replaces the direct inline graph output. It is responsible for:

- showing graph metadata
- showing generation / empty / error states
- surfacing split-map summaries
- opening the fullscreen viewer

It does not attempt to be a live miniature graph. A static, intentional card is easier to scan and avoids squeezing a large tree into an unreadable thumbnail.

### 2. Fullscreen Overlay

The fullscreen overlay is a dedicated knowledge graph modal, separate from the PDF modal. It can borrow existing modal conventions from the codebase, but it should not share DOM IDs or behavior with the PDF viewer.

Responsibilities:

- own the fullscreen presentation
- host toolbar controls
- trap close interactions cleanly
- keep graph exploration separate from the narrow panel layout

### 3. Pan/Zoom Controller

The pan/zoom controller is implemented in `main.js` and manages:

- initial fit-to-screen calculation
- drag-to-pan behavior
- wheel zoom centered on cursor position
- control-button zoom actions
- reset and fit behavior

It works on the viewer stage, not on the panel itself.

### 4. Existing Node Click Integration

The current `[data-kg-payload]` node interaction remains the source of truth for:

- writing `selected-graph-context`
- updating the answer hint
- filling the chat input

The fullscreen viewer must route node clicks into the same binding logic used today so the behavior stays consistent between graph contexts.

## Data Flow

1. Backend builds the graph artifact as it does today.
2. The renderer returns preview-card HTML plus the hidden or overlay-target graph HTML payload.
3. The panel displays only the preview card.
4. User clicks the card.
5. Front-end opens the fullscreen overlay and mounts or reveals the rendered graph stage inside it.
6. Viewer calculates an initial fitted transform.
7. User pans, zooms, or clicks nodes.
8. Node click reuses existing graph payload handling and updates the chat draft state.

No server-side graph contract changes are required for this redesign unless a small metadata addition is useful for the preview card text. That addition must remain backward compatible.

## Error Handling and Edge Cases

### Generating State

If graph generation is in progress, the preview card shows a loading state instead of opening an empty viewer. If useful, the card may remain clickable only after the graph HTML is ready.

### Empty or Failed Graph

If no graph exists or generation failed:

- the card shows an empty or failure explanation
- the refresh button remains available
- the fullscreen viewer does not open into a blank shell

### Multi-Map Graphs

Split graphs remain supported. The preview card shows that the graph has been divided into multiple maps. The fullscreen viewer renders all maps using the current stacked-map semantics.

### Drag Versus Click

Because graph nodes remain clickable, drag detection must use a movement threshold. Small pointer movement should still count as a click. Once the threshold is exceeded, the interaction is treated as pan and the click should not fire.

### Resize Behavior

If the viewport size changes while the fullscreen viewer is open, the viewer should preserve the user's current transform where practical. A manual `Fit` control provides a reliable way to re-center afterward.

## Testing Strategy

### Front-End Behavior

- knowledge graph panel shows a preview card instead of the inline graph
- clicking the card opens the fullscreen overlay
- closing the overlay restores the original page state
- wheel zoom changes scale
- drag pans the graph
- fit and reset controls behave predictably

### Interaction Integrity

- clicking a node inside the fullscreen viewer still writes `graph_context`
- clicking a node still fills the chat input
- clicking a node still does not auto-send
- drag gestures do not accidentally trigger node clicks

### State Coverage

- loading graph state
- ready graph state
- failure graph state
- single-map graph
- split multi-map graph

### Regression Safety

- existing refresh flow remains intact
- knowledge graph status messaging remains visible and meaningful
- current schema v2 output still renders correctly
- split banners and map sections still appear in the fullscreen viewer

## Implementation Notes

- Existing modal conventions in the codebase should be reused where they help with consistency.
- The fullscreen graph overlay must use its own IDs and classes to avoid interfering with the PDF viewer.
- The viewer should be keyboard-safe where feasible, including escape-to-close if consistent with existing UI behavior.
- The graph remains HTML-based in this iteration. If future performance or interaction limits appear, a later project can explore a dedicated SVG or Canvas renderer.

## Acceptance Criteria

- The `Knowledge Graph` area shows a preview card instead of directly rendering the full graph.
- Clicking the preview card opens a fullscreen overlay viewer.
- The fullscreen viewer supports drag-to-pan.
- The fullscreen viewer supports mouse-wheel zoom.
- The fullscreen viewer provides explicit zoom controls and a fit/reset action.
- Clicking graph nodes in the fullscreen viewer still fills the chat input with a suggested question and preserves existing graph context behavior.
- Single-map and multi-map graphs both render correctly in the fullscreen viewer.
- Loading, empty, and failure states remain understandable from the preview card.
