# Tryber for Home Assistant

[![hacs][hacs-badge]][hacs-url]
[![license][license-badge]][license-url]

Unofficial custom integration for the **tester** APIs of
[Tryber](https://app.tryber.me) (AppQuality).
Exposes your earnings, experience points, monthly ranking and available
campaigns as sensors, and notifies you when a new applicable campaign appears.

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[license-badge]: https://img.shields.io/badge/license-MIT-blue.svg
[license-url]: ./LICENSE

## Installation

### HACS (recommended)

1. HACS > Integrations > top-right menu > **Custom repositories**
2. URL `https://github.com/xPudda/TryberHA`, category **Integration**
3. Search for **Tryber**, install and restart Home Assistant

### Manual

1. Copy the `custom_components/tryber` folder to `/config/custom_components/`
2. Restart Home Assistant
3. **Settings > Devices & services > Add integration > Tryber**
4. Enter your **username** (e.g. `first-last`) and **password**

> The username is the account one, it doesn't always match the email.

## Authentication

- Login via `POST /authenticate` with username and password
- The **bearer token** is kept in memory and reused until expiry
  (the API issues it with a 24h validity)
- Automatic renewal 10 minutes before expiry, plus an immediate retry
  on a `401` mid-refresh
- If the password changes, HA starts the **re-authentication** flow

## Polling

Every **2 minutes**, with 4 parallel calls:
`users/me` (selected fields), `users/me/rank`, and two counts on
`users/me/campaigns`.

## Entities created

| Entity | Description |
|---|---|
| `sensor.tryber_net_earnings` | Already paid out earnings (net) |
| `sensor.tryber_gross_earnings` | Already paid out earnings (gross) |
| `sensor.tryber_net_pending_earnings` | Accrued but not yet paid (net) |
| `sensor.tryber_gross_pending_earnings` | Accrued but not yet paid (gross) |
| `sensor.tryber_payout_threshold` | Minimum threshold to request payout |
| `sensor.tryber_experience_points` | Total experience points |
| `sensor.tryber_approved_bugs` | Approved bugs |
| `sensor.tryber_attended_campaigns` | Campaigns you took part in |
| `sensor.tryber_ranking_position` | Position in the monthly ranking |
| `sensor.tryber_monthly_level` | Current level (Bronze, Gold...) |
| `sensor.tryber_monthly_points` | Points for the current month |
| `sensor.tryber_points_to_next_level` | Points missing to the next level |
| `sensor.tryber_available_campaigns` | Campaigns you can apply to |
| `sensor.tryber_accepted_campaigns` | Campaigns you've been selected for |
| `sensor.tryber_latest_available_campaign` | Name of the most recent applicable one |
| `binary_sensor.tryber_payout_threshold_reached` | `on` when you can cash out |

> The entity IDs shown are the ones generated with the device named `Tryber`.
> The integration uses `has_entity_name` and short entity names, so it follows
> the **Settings > System > Entity ID format** setting: if you include the
> area, you'll get e.g. `sensor.studio_tryber_net_earnings`.
> Entity names are in English and are not translated.

## Automation example

```yaml
automation:
  - alias: "Tryber - can cash out"
    triggers:
      - trigger: state
        entity_id: binary_sensor.tryber_payout_threshold_reached
        to: "on"
    actions:
      - action: notify.mobile_app_iphone_16
        data:
          title: "Tryber"
          message: >-
            Threshold reached: {{ states('sensor.tryber_net_pending_earnings') }} EUR
            available to request.

  - alias: "Tryber - new campaigns available"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tryber_available_campaigns
        above: 0
    actions:
      - action: notify.mobile_app_iphone_16
        data:
          message: >-
            There are {{ states('sensor.tryber_available_campaigns') }} campaigns available.
```

## Notification when a new campaign appears

The integration queries `/users/me/campaigns` and keeps only the campaigns
with **`visibility.type == "available"`**, i.e. the ones you can actually
apply to (the others are `candidate` or `unavailable`).

When an id that was never seen before appears, the
**`tryber_new_campaign`** event is fired on the bus with this data:

| Field | Content |
|---|---|
| `id` | Campaign id |
| `name` | Campaign name |
| `start_date` / `end_date` | Campaign dates |
| `close_date` | Application deadline |
| `free_spots` / `total_spots` | Free and total spots |
| `applied` | Whether you've already applied |

Already-seen ids are **persisted to disk**: after an HA restart you won't get
notified again for already-known campaigns. On the very first startup nothing
is notified, only the starting state is recorded.

### Notification automation

```yaml
automation:
  - alias: "Tryber - new campaign available"
    triggers:
      - trigger: event
        event_type: tryber_new_campaign
    actions:
      - action: notify.mobile_app_iphone_16
        data:
          title: "New Tryber campaign"
          message: >-
            {{ trigger.event.data.name }}
            {% if trigger.event.data.free_spots is not none %}
            - {{ trigger.event.data.free_spots }} free spots
            {% endif %}
            {% if trigger.event.data.close_date %}
            (apply by {{ trigger.event.data.close_date }})
            {% endif %}
          data:
            url: "https://app.tryber.me/campaigns/{{ trigger.event.data.id }}"
            push:
              interruption-level: time-sensitive
```

A variant that only notifies if there are free spots:

```yaml
    conditions:
      - condition: template
        value_template: >-
          {{ trigger.event.data.free_spots is none
             or trigger.event.data.free_spots > 0 }}
```

### Related entities

- `sensor.tryber_available_campaigns` - how many there are, with the full list
  in the `campaigns` attribute (useful in templates)
- `sensor.tryber_latest_available_campaign` - name of the first one in the
  list, with id, spots and deadline in the attributes

To list them all in a Markdown card:

```jinja
{% for c in state_attr('sensor.tryber_available_campaigns', 'campaigns') %}
- **{{ c.name }}** ({{ c.free_spots }}/{{ c.total_spots }} spots)
{% endfor %}
```

## Requirements

- Home Assistant **2024.11** or later
- No additional Python dependencies

## Contributing

Pull requests and issues are welcome. The project is released under the
**MIT** license: you can fork, modify and redistribute it, keeping the
copyright notice.

## Disclaimer

**Unofficial** project, not affiliated with nor supported by AppQuality / Tryber.
It only uses user-area endpoints with your own personal credentials.
Mentioned trademarks belong to their respective owners.

## License

[MIT](./LICENSE) (c) 2026 Nicola Rodella
