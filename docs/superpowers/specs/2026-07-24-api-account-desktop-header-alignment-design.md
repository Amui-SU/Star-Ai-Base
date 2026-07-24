# API Account Desktop Header Alignment

## Scope

Only adjust the desktop header of the full-screen API account editor. Mobile
layout, the focused JSON editor, account list, model menu, and other workspace
headers remain unchanged.

## Design

- Keep the existing four-column structure: back button, provider mark, title,
  and actions.
- Use a shared 36px control height for the back button, provider mark, action
  buttons, and close button.
- Align every header item to one vertical center line.
- Tighten the title and save-status line heights so their combined visual
  center matches the provider mark.
- Remove vertical hover movement from the primary action inside this header so
  the control row remains stable.
- Preserve existing colors, labels, behavior, and responsive breakpoints.

## Verification

- Add a focused structure/style regression for the desktop-only header rules.
- Run the relevant frontend tests and lint.
- Verify the rendered editor at a desktop viewport with Playwright, checking
  alignment, overflow, framework overlays, and console errors.
