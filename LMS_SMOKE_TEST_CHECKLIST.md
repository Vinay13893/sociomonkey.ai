# LMS V2 Smoke Test Checklist

## Core

- [ ] Backend health 200; frontend root and tenant login 200.
- [ ] Admin, Manager, Caller, RM, Reception and Platform Owner can authenticate.
- [ ] Role navigation and capability denial behave correctly.
- [ ] Existing Lead list, filters, detail, assignment and history work.
- [ ] Upload/import and export remain separate and bounded.

## V2 Workflows

- [ ] Organisation and permission changes remain tenant-scoped.
- [ ] Status/source display configuration preserves internal keys.
- [ ] Location and Meeting Room CRUD works.
- [ ] Visit lifecycle and Gallery/Reception handoff work.
- [ ] Channel Partner profile, assignment and Visit link work.
- [ ] Role-specific Action Boards load and update.
- [ ] Pipeline transitions append immutable history and configured Actions.
- [ ] Reports aggregate correctly and exports download separately.

## Integrations and Workers

- [ ] Meta OAuth returns to the canonical backend.
- [ ] Signed webhook creates one Lead; repeated delivery is deduplicated.
- [ ] Source/form/project mappings are preserved.
- [ ] Assignment creates bell and queued push events.
- [ ] Callback creates one due reminder and one push event.
- [ ] Drain and reminder workers complete two scheduled runs without overlap.
- [ ] Queue pending age, failures and dead letters remain within thresholds.

## PWA

- [ ] Install/update on Android and iOS.
- [ ] Subscription registration and renewal work.
- [ ] Foreground/background push arrives.
- [ ] Notification click opens the correct tenant context.
