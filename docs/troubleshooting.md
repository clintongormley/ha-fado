# Troubleshooting

## Enable logging

Fado logs through Home Assistant's standard logger, so you raise its verbosity
the same way as any other integration.

**From the UI:** go to **Settings → Devices & Services**, open the **Fado**
integration, click the **⋮** menu and choose **Enable debug logging**. Reproduce
the problem, then choose **Disable debug logging** to download the captured log.

**From `configuration.yaml`** (lets you pick the level, and persists across
restarts):

```yaml
logger:
  logs:
    custom_components.fado: info # or: debug
```

| Level     | What it shows                                                                        |
| --------- | ------------------------------------------------------------------------------------ |
| `warning` | Default. Only logs exceptions.                                                       |
| `info`    | Fade start/complete, manual interventions, brightness restoration, autoconfiguration |
| `debug`   | Every brightness step, expected state tracking, task cancellation internals          |

For most troubleshooting, `info` level is sufficient and easier to follow.

## Known problems

Different lights behave differently, and these differences can create problems.

### Rounding

The values set by Fado are not necessarily what the light reports back. For
instance, Fado sets a brightness of `50%` but the light reports a brightness of
`51%`. Fado uses rounding to try to match these values regardless.

### Missing and extra events

A light may compress several actions into a single event, so while applying a
fade step the user turns the light off. This manual intervention may be ignored
by the light and so the fade loop continues. Alternatively, maybe the light-off
event is reported and the fade step never generates an event.

When using [native transitions](panel.md#native-transitions), the light may emit state
update events which are mid-range, e.g. a fade step is intended to move the
light from brightness `50` to brightness `65`, but the light may also report an
intermediate brightness state of `55`. Intermediate steps are recognised but are
not removed from the list of expected states as the light should later report a
final state which matches the `50->65` change.

Fado maintains an expected-events list internally. These events are pruned after
3 seconds so that, even if things do occasionally go wrong, within 3 seconds
the light should be functioning normally again.

## Reporting issues

If you encounter a bug, please
[open an issue](https://github.com/clintongormley/ha-fado/issues/new/choose)
with:

- Your Home Assistant version
- The integration version
- Debug logs showing the problem
- Diagnostic data (available from the
    [**Autoconfiguration Panel**](panel.md#autoconfiguration-panel))
- Steps to reproduce
