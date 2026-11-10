# 42 Intra for Home Assistant

Follow a 42 student's logtime, campus presence, level, wallet and evaluation points in
Home Assistant, using the official 42 API.

Requires Home Assistant **2026.3** or newer.

<img width="1567" height="852" alt="image" src="https://github.com/user-attachments/assets/b7664b23-4952-4de3-8613-8e72c01300da" />

## Installation

### Marketplace (HACS)

1. Go to **Settings → Marketplace → ⋮ → Custom repositories**.
2. Add `https://github.com/harmonie-durrant/ft_homeassistant` with category **Integration**.
3. Install **42 Intra**, then restart Home Assistant.

### Manual

1. Download `ft_homeassistant.zip` from the
   [latest release](https://github.com/harmonie-durrant/ft_homeassistant/releases/latest).
2. Extract it into `config/custom_components/ft_homeassistant/`.
3. Restart Home Assistant.

## Setup

1. On the [42 API applications page](https://profile.intra.42.fr/oauth/applications), create a
   new application. Any name works; the redirect URI isn't used (enter
   `http://localhost` if a value is required). Keep the default `public` scope.
2. In Home Assistant go to **Settings → Devices & services → Add integration → 42 Intra**.
3. Enter the application **UID**, its **secret**, and the **login** of the student to follow.

To follow several students, add the integration once per login. They can share the same
application.

## What gets created

One device per student (named after their display name), with:

| Entity | Description |
| --- | --- |
| Logtime today / this week / this month | Hours logged on campus computers. The week starts on Monday. Days follow your Home Assistant time zone. |
| Logged in | On while the student is logged in on a campus computer. |
| Location | The computer the student is logged in on (for example `c1r2p3`), unknown when logged out. |
| Level | Level in the main 42 cursus (falls back to the latest cursus, for example the Piscine). The cursus name and grade are attributes. |
| Wallet | Wallet balance in ₳. |
| Evaluation points | Available evaluation (correction) points. |
| Refresh | Button that fetches the data right away. |
| Application secret expiry | Diagnostic. Only created if the 42 API reports when the application secret expires. |

## Options

**Settings → Devices & services → 42 Intra → Configure**:

- **Refresh interval**: how often the data is fetched, from 5 to 120 minutes (15 by default).

To change the application UID or secret, use **⋮ → Reconfigure** on the entry. Leave the
secret empty to keep the current one.

## Notes

- Each refresh uses 2 API requests (profile + logtime), plus one to renew the access token every
  2 hours. The 42 API allows 1200 requests per hour per application, so many students can share
  an application.
- If the rate limit is reached, the last values are kept and a warning is logged.
- 42 application secrets expire and must be replaced on the applications page. When the secret is
  refused, Home Assistant shows a **Reauthenticate** notification asking for the new one. If the
  API reports the expiry date, the request appears 3 days before it.

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.ft_homeassistant: debug
```

or with **Enable debug logging** on the integration page. Each refresh logs a line such as
`Fetched hdurrant (id …3456): location=c1r2p3, 4 logtime days since 2026-11-01`.

- `invalid_auth` during setup: the UID or secret is wrong, or the secret has expired.
- `user_not_found`: check the login spelling (it is the intra login, not the display name).

## Development

```bash
scripts/setup      # .venv with the pinned Home Assistant
scripts/develop    # runs Home Assistant with this integration on http://localhost:8123

python3 -m venv .venv-test
.venv-test/bin/pip install -r requirements_test.txt
.venv-test/bin/pytest -q
```

## License

[MIT](LICENSE)
