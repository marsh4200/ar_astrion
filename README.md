# AR Astrion Remote

Home Assistant integration for a **Sanytron Astrion HA100** running
[Astrion Custom Dashboard](https://github.com/dckiller51/astrion-custom-dashboard).

The app on the remote already talks to Home Assistant by itself — it holds a
long-lived token and speaks the websocket API directly. This integration is the
other half: it makes the remote a **device** in Home Assistant, so every
physical button becomes an automation trigger and the remote's own state
becomes entities you can see and drive.

## What you get

| Entity | What it does |
| --- | --- |
| `event.*` — one per button | Fires on every press, **bound or not**, with `short` / `long` event types. All 22 reportable buttons, plus a catch-all for anything unrecognised. |
| `select.*_page` | The dashboard page on screen. Reads back swipes and hardware presses, and setting it jumps the remote. |
| `select.*_<room>_activity` | Which AV Activity is running in a room; pick one to start it, `Off` to stop it. |
| `sensor.*_battery` + `binary_sensor.*_charging` | Charge level and dock state. |
| `button.*_ring` / `button.*_stop_ringing` | Find the remote down the back of the sofa. |
| `update.*_firmware` | Installed app version against the newest published release, with install. |

Services: `ar_astrion.push_dashboard` (replace `dashboard.json` and live-reload
it) and `ar_astrion.ring` (with sound, volume and duration).

## Why the buttons matter

Without this, a physical button can only do what `dashboard.json` says it does
— you edit a JSON file on the device and reload it. With it, every press
arrives in Home Assistant as an event, so the mapping lives in an automation
you can change from the UI:

```yaml
automation:
  - alias: "Remote red button — movie mode"
    triggers:
      - trigger: state
        entity_id: event.astrion_remote_red
    conditions:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.event_type == 'short' }}"
    actions:
      - action: script.turn_on
        target:
          entity_id: script.movie_mode
```

Each event carries useful attributes:

- `key` — the logical button (`RED_BUTTON`, `CENTER`, …)
- `key_code` — the raw Android keycode, for a button this integration doesn't
  know by name
- `bound` — whether a `dashboard.json` binding *also* ran for that press. Check
  it when a button is configured both locally and here, so one press doesn't
  get handled twice.
- `page` — which dashboard page was on screen, letting one button mean
  different things per page

### Local bindings still win on speed

Both layers work at once. A binding in `dashboard.json` fires instantly and
keeps working with Home Assistant down (IR and Harmony paths don't involve HA
at all); an automation off an event entity costs 100–300 ms and needs HA up.
Keep AV keys you press constantly — volume, transport, input — bound locally,
and put everything else here.

## Requirements

- Home Assistant 2025.2 or newer
- Astrion Custom Dashboard on the remote, from a build that includes
  `POST /webhook-id` (needed for pushes — without it, setup will say so and
  everything else still works by polling)
- The remote's configuration server enabled (it is by default; the address
  shows in the Settings panel on the remote itself)

## Install

**HACS** → ⋮ → Custom repositories → `https://github.com/marsh4200/ar_astrion`,
category *Integration* → install → restart Home Assistant.

**Manually** — copy `custom_components/ar_astrion` into your
`config/custom_components/` and restart.

Then **Settings → Devices & services → Add integration → AR Astrion Remote**
and enter the remote's IP. Setup registers a webhook and writes its id to the
remote for you, so pushes start immediately.

## How it talks to the remote

Two channels, split by direction:

- **HA → remote**: `http://<remote-ip>:8080` — the app's own configuration
  server. Unauthenticated and LAN-only by design, so don't expose it.
- **remote → HA**: `POST /api/webhook/<id>` — the remote pushes button
  presses, page changes, Activity changes and battery the moment they happen.

Polling runs every 10 minutes purely as a backstop for a missed push. That's
deliberate: this is a battery-powered handheld that sleeps most of the day, and
a tight polling loop is exactly what keeps its Wi-Fi radio awake and flattens
the battery you're trying to measure.

The webhook id is re-asserted on every setup, because the remote stores it in
its own preferences — a reinstall, a factory reset, or someone saving the web
configurator's connection form with that field blank would otherwise stop the
pushes silently.

The full device contract lives in the app repo as
[`docs/COMPANION_INTEGRATION.md`](https://github.com/dckiller51/astrion-custom-dashboard/blob/dev/docs/COMPANION_INTEGRATION.md).

## Notes and limits

- **The POWER button can never be reported.** Android's window manager
  swallows every real `KEYCODE_POWER` press before any app sees it. The remote
  has no way around that, so there's no entity for it.
- **`update` install is a request, not a result.** The remote downloads the
  APK and opens Android's installer; "install unknown apps" must be granted
  for Astrion, and someone has to tap through it on the remote. The installed
  version won't change until the app restarts.
- **Latest version comes from GitHub, not the remote.** The device's own
  `/check-update` answers with an HTML redirect written for a browser, so this
  integration reads the releases API instead. Point it at a fork's repo in the
  integration's options if you publish your own builds.
- **Activity selects are created at setup.** A room added to `dashboard.json`
  afterwards needs a reload of the entry before its select appears.
- **One entry per remote**, identified by `host:port`.

## Licence

MIT — see [LICENSE](LICENSE).
