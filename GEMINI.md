# Core User Preferences & Interaction Rules

## 1. Interactive Questioning Style (Default Behavior)
- **Always Clarify with Interactive Questions**: Whenever requirements are underspecified, have multiple viable paths, involve UX/UI design choices, or require clarification, ALWAYS formulate the questions using the interactive multiple-choice question tool (`ask_question`).
- **Targeted Options**: Present clear, concrete, well-thought-out options with a recommended choice prefixed with `(Recommended)`.
- **Avoid Guessing**: Never make assumptions about user preferences when an interactive question can confirm their intent directly.

## 2. Design & UX Principles
- **Simplicity Above All**: The user loves clean simplicity and strongly dislikes visual clutter, crowded layouts, or unnecessary decorative elements.
- **Fast & Responsive (No Sluggish Animations)**: Avoid slow layout sliding, bouncy layout shifts (`layout` prop on broad lists), or sluggish CSS dimension transitions. Actions (like opening/closing menus or batch settings) must feel instant, snappy, and solid.
- **Mobile-Friendly Single Rows**: Maintain single-row layouts for titles and toggles on mobile without awkward wrapping.
- **Direct Card Surface Toggling**: In card lists (like combat or prestige tasks), ensure clicking anywhere on the outer card component toggles the task cleanly without conflicting with child inputs.
