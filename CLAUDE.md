# CLAUDE.md — Home Assistant custom integration (HACS)

Base instructions for building and publishing a Home Assistant custom integration distributed
through HACS (shown as **Settings → Marketplace** in Home Assistant 2026.11+).
Replace `<domain>`, `<Name>`, `<owner>/<repo>` with the project's values.

## Working with the user

- **Commits:** never commit or push without asking. Before every commit, ask for the title with
  2 suggested options (AskUserQuestion), and offer "commit & push only", "commit & release" or
  "don't commit yet" when it matters.
- **Commit titles:** Conventional Commits, lowercase, imperative, no trailing period:
  `feat: …`, `fix: …`, `docs: …`, `chore: …`, `build: …`. One feature or fix per commit.
- **Commit body:** always end with the `Co-Authored-By` trailer given by the harness.
- **Branch:** work and push directly on `main` (solo project), unless told otherwise.
- **Before committing:** run the tests, remove `__pycache__/`, check `git status` contains only
  the intended files.
- **Pasted CI errors** (hassfest, HACS action) mean "fix it": fix, test, then ask for the commit
  title.
- **Verify before claiming:** check the API documentation and the installed Home Assistant
  sources (`.venv/lib/python3.*/site-packages/homeassistant/`) instead of relying on memory.
  Deprecations change every release.
- **Report honestly:** say what was tested with mocks versus a real instance or real API.

## Versioning and releases

- Semantic versioning, `0.x` while young: `feat` → minor (`0.3.0` → `0.4.0`),
  `fix`/docs-only → patch (`0.1.1` → `0.1.2`).
- The version lives in `custom_components/<domain>/manifest.json` only.
- Release flow (after the feature commit is pushed and the user agreed to release):
  1. `python3 scripts/build_release.py X.Y.Z`. It sets the manifest version and builds
     `dist/<domain>.zip`.
  2. Commit `chore: release X.Y.Z`, then push.
  3. `gh release create vX.Y.Z dist/<domain>.zip --title vX.Y.Z --notes-file <notes.md>`
- Before starting changes on a released version, build the zip and keep a copy
  (`dist/<domain>-X.Y.Z.zip`).
- **Release notes** are written for end users installing from the Marketplace, not developers.
  - Sections, only those that apply: `## New`, `## Improved`, `## Fixed`, `## Upgrade notes`,
    `## Known limitations`.
  - Bold lead phrase per bullet, then what it means for the user and where to find it in the UI.
  - End with `**Full Changelog**: https://github.com/<owner>/<repo>/compare/vPREV...vX.Y.Z`.
  - Write them to a file in the scratchpad, never inline in the command.

## Repository layout

```
custom_components/__init__.py        # empty package file, needed by the tests (see Testing)
custom_components/<domain>/
  __init__.py        # async_setup_entry / async_unload_entry / async_remove_entry
  manifest.json
  const.py
  api.py             # API client: no Home Assistant imports, typed exceptions
  coordinator.py     # DataUpdateCoordinator + typed ConfigEntry alias
  config_flow.py     # user / reauth / reconfigure steps + OptionsFlow
  entity.py          # base CoordinatorEntity with DeviceInfo
  sensor.py, button.py, …
  strings.json       # source of truth (English)
  translations/en.json   # identical copy of strings.json
  translations/fr.json   # (other languages)
  brand/icon.png     # 256×256, plus brand/icon@2x.png 512×512
config/configuration.yaml   # dev instance config (only file committed in config/)
scripts/setup, scripts/develop, scripts/build_release.py
tests/conftest.py, tests/test_*.py
hacs.json, README.md, LICENSE, pytest.ini
requirements_dev.txt   # homeassistant==<pinned>
requirements_test.txt  # pytest-homeassistant-custom-component
.github/workflows/validate.yml   # hassfest + HACS action + tests
```

`.gitignore`: `__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `.pytest_cache/`, `dist/`,
`config/*` followed by `!config/configuration.yaml`.

## manifest.json

Key order: `domain`, `name`, then alphabetical (hassfest checks this).

```json
{
  "domain": "<domain>",
  "name": "<Name>",
  "after_dependencies": ["recorder"],
  "categories": ["<category>"],
  "codeowners": ["@<owner>"],
  "config_flow": true,
  "documentation": "https://github.com/<owner>/<repo>",
  "integration_type": "service",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/<owner>/<repo>/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

- `categories` is required: 1–3 values from
  https://contributors.home-assistant.io/core/integrations/categories/ (for example `finance`,
  `energy`, `climate`, `sensors`). Without it, hassfest warns that the manifest has no categories.
- List in `after_dependencies` (or `dependencies`) every integration you import from, for
  example `recorder` for statistics.
- Don't add `requirements` that Home Assistant already ships (aiohttp, PyJWT, cryptography…).
  Pin exact versions for anything else.
- `domain` can never change after release. Never reuse a core integration's domain.

## hacs.json

```json
{
  "name": "<Name>",
  "homeassistant": "2026.3.0",
  "render_readme": true,
  "zip_release": true,
  "filename": "<domain>.zip"
}
```

- `homeassistant` is the minimum version. Keep it as low as the code really allows (2026.3 is
  the first version that shows `brand/` icons) so more users can install.
- With `zip_release: true`, every GitHub release **must** have the zip attached, with the
  integration files at the zip root. Otherwise installs fail.
- `country` (optional) limits the listing to some countries. Only use it if the integration
  really is country-specific.

## Translations (hassfest rules)

- `strings.json` and `translations/en.json` must be identical. Edit them with a small Python
  script that loads, edits and re-dumps all language files (`ensure_ascii=False`, indent 2).
- **No URLs in strings.** Use description placeholders: `"[panel]({panel_url})"` plus
  `description_placeholders={"panel_url": URL}`.
- **Keys** match `[a-z0-9-_]+` and can't start or end with `-` or `_`. Selector option values are
  translation keys, so they must be lowercase. Convert to the API's casing in code (`.upper()`).
- Structure: `config.step.<id>.{title,description,data,data_description}`, `config.error`,
  `config.abort` (include `reauth_successful`, `reconfigure_successful`), `config.create_entry`,
  `options.step.init…`, `options.error`, `selector.<key>.options`,
  `entity.<platform>.<translation_key>.name`.
- Check the keys before committing:
  ```bash
  python3 - <<'EOF'
  import json,re,glob
  pat=re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")
  for p in glob.glob("custom_components/*/strings.json")+glob.glob("custom_components/*/translations/*.json"):
      bad=[]
      def walk(o,path=""):
          if isinstance(o,dict):
              for k,v in o.items():
                  if not pat.match(k): bad.append(path+"."+k)
                  walk(v,path+"."+k)
      walk(json.load(open(p))); print(p, bad or "ok")
  EOF
  ```

## Integration patterns that work

- **Config flow**
  - **`user` step:** validate credentials with a real API call before creating the entry.
    Map exceptions to `errors["base"]`: `invalid_auth`, `cannot_connect`, …
  - **Unique id:** derive `async_set_unique_id` from a stable account or device identifier, then
    call `_abort_if_unique_id_configured()`.
  - **Secrets in forms:** never prefill secrets. In reconfigure, an empty field means "keep the
    current value".
  - **Long or OAuth-like auth without a public callback:** show the authorization link as a
    description placeholder, and ask the user to paste back the URL they land on. Check `state`
    and parse `code`/`error` from it.
- **Re-authentication:** raise `ConfigEntryAuthFailed` from the coordinator.
  - Implement `async_step_reauth` (stores `entry_data`) and `async_step_reauth_confirm`, then
    finish with `self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=…)`.
  - Refuse when the re-authenticated account doesn't match the original one (`wrong_account`).
  - If credentials expire on a known date, call `entry.async_start_reauth(hass)` some days
    before, and expose the expiry as a `TIMESTAMP` diagnostic sensor.
- **Reconfigure:** `async_step_reconfigure` with `self._get_reconfigure_entry()`, finishing with
  `async_update_reload_and_abort`. Use it to change credentials without losing entities.
- **Options:** subclass `OptionsFlowWithReload`, so the entry reloads on save. Use
  `add_suggested_values_to_schema(schema, self.config_entry.options)`. Coerce `NumberSelector`
  values to `int`.
- **Runtime data:**
  - Alias the entry type: `type <X>ConfigEntry = ConfigEntry[<X>Coordinator]`, and use
    `entry.runtime_data` (no `hass.data`).
  - Pass `config_entry=entry` to `DataUpdateCoordinator`.
  - Put one-off async setup in `_async_setup()`.
  - Call `await coordinator.async_config_entry_first_refresh()` before forwarding platforms.
- **Rate-limited or quota APIs** (banks, cloud APIs with daily limits):
  - Persist the last raw API data with `helpers.storage.Store` (`f"{DOMAIN}.{entry_id}"`) and reuse
    it while it's younger than the update interval minus a margin. That way restarts, reloads and
    option changes don't spend requests.
  - On a rate-limit error, keep returning the last data, log a warning, and count the attempt as a
    fetch.
  - A "Refresh" button forces a fetch.
  - Store **raw** responses, not derived values, so option changes can be applied from the cache.
  - Delete the store in `async_remove_entry`.
- **Entities**
  - Use a base class with `_attr_has_entity_name = True`, `translation_key`, a stable
    `unique_id` (`f"{stable_id}_{key}"`) and `DeviceInfo(identifiers={(DOMAIN, stable_id)}, …,
    entry_type=DeviceEntryType.SERVICE)` for cloud services.
  - Use `device_class` and `state_class` correctly. `MONETARY` only allows `state_class=TOTAL`.
  - Diagnostic entities get `entity_category=EntityCategory.DIAGNOSTIC`.
- **Removing devices:** remove devices of items no longer selected with
  `dev_reg.async_remove_device(device.id)`. `async_get_device(identifiers=…)` is deprecated; use
  `async_get_device_by_identifier((DOMAIN, id), entry_id)`.
- **Background work:** use `entry.async_create_background_task(hass, coro, name)` for slow jobs
  such as a history import. Use a flag in `entry.data` for one-shot jobs, cleared in `finally`.
- **Importing history** into the long-term statistics of an existing sensor:
  - Call `async_import_statistics(hass, metadata, rows)` with
    `StatisticMetaData(mean_type=StatisticMeanType.NONE, has_sum=True, source="recorder",
    statistic_id=<entity_id>, unit_class=None, unit_of_measurement=…, name=None)`.
  - Rows are `StatisticData(start=<aware datetime at :00>, state=…, sum=…)`, for completed hours
    only.
  - Never import over hours that are already recorded: query the first row with
    `statistics_during_period` in the recorder executor.
  - Align `sum` with existing rows to avoid jumps.
- **API client**
  - Read the provider's API reference first: endpoints, auth, error codes, pagination, enum
    values.
  - Map error codes to typed exceptions: auth, session or expired, rate limit, generic.
  - Use the shared `async_get_clientsession(hass)`. Catch `ClientError` and `TimeoutError`.
- **Logging and privacy**
  - Never log secrets, tokens or full identifiers. Mask them (`…1234`).
  - Log useful structure at `info`/`debug` level (what the API returned, what was skipped and
    why), so users can debug with `logger: logs: custom_components.<domain>: debug`.
  - Surface skipped items in the UI where possible (for example `create_entry` description
    placeholders).
- **Choosing items:** when the API returns several items (accounts, devices), let the user pick
  in a multi-select step. Show useful live values in the option labels, flag suspicious items and
  leave them unticked by default. Reuse the data fetched for that screen as the first cache.

## Local development

- `scripts/setup` creates `.venv` with `homeassistant==<pinned>` from `requirements_dev.txt`
  only. Don't install the test plugin there: it pins an exact Home Assistant version, and pip
  silently downgrades to an ancient plugin if none matches.
- `scripts/develop` links `config/custom_components/<domain>` to the repo's integration folder,
  then loops on `.venv/bin/hass --config config` while the exit code is 100 (a restart requested
  from the UI).
- `config/configuration.yaml`: `default_config:` plus a `logger:` block with
  `custom_components.<domain>: debug`.
  - Don't put an `http:` block in it: YAML HTTP config is deprecated. Proxy settings for
    Codespaces or VS Code port forwarding (Use X-Forwarded-For, trusted proxies `127.0.0.1`,
    `::1`) go in **Settings → System → Network**.
- **Python code is not reloaded** when a config entry reloads: restart Home Assistant after code
  changes, before testing in the UI.
- Logs are in `config/home-assistant.log`. Errors about go2rtc, ffmpeg, libpcap or libturbojpeg
  in a dev container are expected noise.
- Home Assistant 2026.x requires Python ≥ 3.14.2.

## Testing

- Use `pytest-homeassistant-custom-component` in a separate venv (`requirements_test.txt`).
  `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`.
- The test harness ships its own `custom_components` package. To make the repo's integration load:
  - keep an empty `custom_components/__init__.py`;
  - `import custom_components.<domain>` at the top of `tests/conftest.py`;
  - add an autouse fixture requesting `enable_custom_integrations`.
- Mock HTTP with `aioclient_mock`. For query parameters, register mocks with `params=`, the most
  specific first.
- Use `MockConfigEntry` with `entry.start_reauth_flow(hass)` and
  `entry.start_reconfigure_flow(hass)`, and `hass_storage` to seed `Store` data.
- Wait for background tasks with `await hass.async_block_till_done(wait_background_tasks=True)`.
- **The recorder fixtures (`recorder_mock`) fail on Python 3.14** (lazy annotations).
  - Mock the integration's recorder helpers (the lookup function and `async_import_statistics`)
    and assert on what's passed to them.
  - Verify the real recorder separately with a throwaway script in `.venv`:
    `bootstrap.async_load_base_functionality`, `recorder_helper.async_initialize_recorder`, then
    `async_setup_component(hass, "recorder", …)`.
- The newest Home Assistant may not have a matching test plugin yet. Tests then run on the
  previous Home Assistant version. Also import-check the integration in `.venv` (the newest
  Home Assistant).

## CI (`.github/workflows/validate.yml`)

Three jobs, on push, pull request, daily schedule and manual dispatch:
- `home-assistant/actions/hassfest@master` (after `actions/checkout`)
- `hacs/action@main` with `category: integration`
- tests: `actions/setup-python` (3.14), `pip install -r requirements_test.txt`, `pytest -q`

## HACS / Marketplace

**How users install:**
1. **Settings → Marketplace → ⋮ → Custom repositories.**
2. Add `https://github.com/<owner>/<repo>` with category **Integration**.
3. Install, restart Home Assistant.
4. **Settings → Devices & services → Add integration.**

Once the repository is in the HACS default list, step 2 isn't needed. HACS installs the release
zip (with `zip_release`) or the `custom_components/<domain>` folder, and shows the README.

**Requirements for inclusion in the default list**
(https://hacs.xyz/docs/publish/include/):
- **Repository:** public on GitHub, owned by you or with you as a major contributor (no
  organization-only PR), not archived. Has a **description**, **topics**, and **issues enabled**.
- **License:** GitHub must detect it, and it must be OSI-approved (MIT is fine).
- **CI:** the HACS action **and** hassfest pass with no errors and nothing ignored.
- **Releases:** at least one **full GitHub release**, not just a tag, created after the actions
  pass.
- **Files:** `hacs.json` has `name`; `manifest.json` is valid.
- **Brand:** a `brand/icon.png` in the integration (or the domain already in
  home-assistant/brands).
- **Scope:** no alpha or beta integrations, and nothing that overrides a core integration or
  clashes with a core domain. Remove "work in progress" wording from the README and test with a
  real instance and real API first.

**Submitting:**
1. Fork `hacs/default` and branch from `master`.
2. Add `"<owner>/<repo>"` to the `integration` file **in alphabetical order** (the lint checks
   sorting and JSON).
3. Fill in the PR template completely.

Draft means minor issues; closed means major ones. Review can take months.

## README sections

1. Title and one-line description, then the minimum Home Assistant version.
2. **Installation:** Marketplace custom repository steps, then manual install.
3. **Setup:** provider account, credentials, the config flow steps.
4. What gets created: devices and entities.
5. **Options**, plus how to change credentials (Reconfigure).
6. **Notes:** refresh interval, rate limits, caching, expiry and re-authentication.
7. **Troubleshooting:** how to enable debug logging and what log lines to look for.
8. **Development:** `scripts/setup`, `scripts/develop`, tests.
9. License.
