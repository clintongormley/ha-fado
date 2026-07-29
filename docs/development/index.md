# Development

## Testing

The integration includes a comprehensive test suite covering config flow,
action handling, fade execution, color fading, manual interruption detection,
and brightness restoration.

### Prerequisites

Install the test dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov pytest-homeassistant-custom-component syrupy
```

!!! note

    Do not use `pip install -e .` (editable install) as it conflicts
    with `pytest-homeassistant-custom-component`'s custom component discovery
    mechanism.

### Running Tests

Run all tests:

```bash
pytest tests/ -v
```

Run tests with coverage report:

```bash
pytest tests/ --cov=custom_components.fado --cov-report=term-missing -v
```

Run a specific test file:

```bash
pytest tests/test_fade_execution.py -v
```

### Test Coverage

The pre-push hook enforces a minimum of 90% code coverage, and the suite
includes tests for:

- **Config flow** (`test_config_flow.py`): User setup, import flow, options
    validation
- **Integration setup** (`test_init.py`): Action registration, storage loading,
    unload cleanup
- **Action handling** (`test_actions.py`): Entity ID formats, group expansion,
    default parameters
- **Fade execution** (`test_fade_execution.py`): Fade up/down, turn off at 0%,
    non-dimmable lights
- **Color parameters** (`test_color_params.py`): Color conversions, validation,
    `from:` parameter
- **Capability filtering** (`test_capability_filtering.py`): Light capability
    detection, unsupported mode handling
- **Step generation** (`test_step_generation.py`): Hue interpolation, hybrid
    transitions
- **Planckian locus** (`test_planckian_locus.py`): Color temperature to HS
    conversions
- **Manual interruption** (`test_manual_interruption.py`): Brightness/color
    change detection, fade cancellation
- **Brightness restoration** (`test_brightness_restoration.py`): Restore on
    turn-on, storage persistence
- **Exclude/include actions** (`test_exclude_action.py`): Action registration,
    flag persistence, fade filtering, panel notification
- **Event waiting** (`test_event_waiting.py`): Condition-based event waiting,
    stale value pruning

## Continuous integration

Tests run automatically on push and pull requests via GitHub Actions. The
workflow tests against Python 3.13.

## Building the documentation site

The site is two builds assembled into one directory: the interactive demo at the
root, and this documentation under `/docs/`.

```bash
pip install -r requirements-docs.txt   # once
mkdocs serve                            # docs only, live reload

cd demo && npm install && npm run dev:pages   # demo only, live reload

PAGES_BASE_PATH=/ scripts/build_site.sh   # the whole site, for local preview
python3 -m http.server -d dist            # then browse http://localhost:8000/
```

`scripts/build_site.sh` runs `mkdocs build --strict`, so a broken internal link
fails the build rather than shipping. `PAGES_BASE_PATH=/` builds the demo with
root-relative asset paths, which is what makes them resolve when `dist/` is
served at `http://localhost:8000/`; the default build (no env var) targets
`/ha-fado/` to match GitHub Pages, and its assets 404 at the plain root.

To check the site exactly as it deploys — assets served from `/ha-fado/` —
build with the default base path and serve through a symlink that reproduces
that prefix:

```bash
scripts/build_site.sh                     # the whole site, exactly as deployed
mkdir -p /tmp/fado-serve && ln -sfn "$PWD/dist" /tmp/fado-serve/ha-fado
python3 -m http.server -d /tmp/fado-serve  # then browse http://localhost:8000/ha-fado/
```

## Credits

The interactive demo was originally created by
[Florian Horner](https://github.com/florianhorner)
([source](https://github.com/florianhorner/fado-light-fader-demo), 0BSD) and is
vendored into `demo/` with permission. See `demo/UPSTREAM.md` for the pinned
commit and re-sync instructions.
