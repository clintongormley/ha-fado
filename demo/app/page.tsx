"use client";

import {
  Check,
  Copy,
  ExternalLink,
  Github,
  Hand,
  Lightbulb,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { BedroomScene } from "./components/BedroomScene";
import { SignatureDemo } from "./components/SignatureDemo";
import { copyTextWithFallback } from "./copy-text.mjs";
import { getWallSwitchResult } from "./demo-state.mjs";

type Mode = "fado" | "basic";
type Easing = "auto" | "linear" | "ease_in_out_sine";

type Scenario = {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  fromBrightness: number;
  targetBrightness: number;
  fromHue: number;
  targetHue: number;
  targetLabel: string;
  yaml: string;
};

const scenarios: Scenario[] = [
  {
    id: "bedtime",
    eyebrow: "Wind down",
    title: "Bedtime fade",
    description: "Ease the bedroom from a warm 80% to off.",
    fromBrightness: 80,
    targetBrightness: 0,
    fromHue: 38,
    targetHue: 24,
    targetLabel: "Off",
    yaml: `action: fado.fade_lights
target:
  area_id: bedroom
data:
  brightness_pct: 0
  transition: 15
  easing: auto`,
  },
  {
    id: "sunrise",
    eyebrow: "Wake gently",
    title: "Sunrise fade",
    description: "Bring a barely-lit room up to a clear 92%.",
    fromBrightness: 2,
    targetBrightness: 92,
    fromHue: 24,
    targetHue: 43,
    targetLabel: "92%",
    yaml: `action: fado.fade_lights
target:
  area_id: bedroom
data:
  brightness_pct: 92
  color_temp_kelvin: 4200
  transition: 15
  easing: auto`,
  },
  {
    id: "color",
    eyebrow: "Shift the mood",
    title: "Warm to violet",
    description: "Experience a hybrid white-to-color transition.",
    fromBrightness: 62,
    targetBrightness: 78,
    fromHue: 38,
    targetHue: 276,
    targetLabel: "Violet · 78%",
    yaml: `action: fado.fade_lights
target:
  entity_id: light.accent
data:
  hs_color: [276, 74]
  brightness_pct: 78
  transition: 15`,
  },
];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function interpolateHue(from: number, to: number, progress: number) {
  let delta = to - from;
  if (Math.abs(delta) > 180) {
    delta += delta > 0 ? -360 : 360;
  }
  return (from + delta * progress + 360) % 360;
}

function ease(progress: number, easing: Easing, rising: boolean) {
  if (easing === "linear") return progress;
  if (easing === "ease_in_out_sine") {
    return -(Math.cos(Math.PI * progress) - 1) / 2;
  }
  return rising
    ? progress * progress
    : 1 - (1 - progress) * (1 - progress);
}

export default function Home() {
  const [scenarioId, setScenarioId] = useState("bedtime");
  const [mode, setMode] = useState<Mode>("fado");
  const [transition, setTransition] = useState(15);
  const [easing, setEasing] = useState<Easing>("auto");
  const [brightness, setBrightness] = useState(80);
  const [hue, setHue] = useState(38);
  const [progress, setProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const [isOff, setIsOff] = useState(false);
  const [interrupted, setInterrupted] = useState(false);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "manual">(
    "idle"
  );
  const [status, setStatus] = useState(
    "Ready. Fado remembers this room at 80%."
  );
  const animationRef = useRef<number | null>(null);
  const yamlCodeRef = useRef<HTMLElement | null>(null);
  const scenario =
    scenarios.find((item) => item.id === scenarioId) ?? scenarios[0];

  const cancelAnimation = () => {
    if (animationRef.current !== null) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  };

  const resetDemo = (nextScenario = scenario, nextMode = mode) => {
    cancelAnimation();
    setRunning(false);
    setInterrupted(false);
    setProgress(0);
    setBrightness(nextScenario.fromBrightness);
    setIsOff(false);
    setHue(nextScenario.fromHue);
    setStatus(
      nextMode === "fado"
        ? `Ready. Fado remembers this room at ${nextScenario.fromBrightness}%.`
        : "Ready. A basic light call has no Fado coordination layer."
    );
  };

  useEffect(() => {
    return () => cancelAnimation();
  }, []);

  const chooseScenario = (nextId: string) => {
    const nextScenario =
      scenarios.find((item) => item.id === nextId) ?? scenarios[0];
    setScenarioId(nextId);
    resetDemo(nextScenario);
  };

  const chooseMode = (nextMode: Mode) => {
    setMode(nextMode);
    resetDemo(scenario, nextMode);
  };

  const runDemo = () => {
    cancelAnimation();
    const startBrightness = scenario.fromBrightness;
    const startHue = scenario.fromHue;
    const rising = scenario.targetBrightness > startBrightness;
    const demoDuration = clamp(transition * 360, 3400, 7600);
    const startedAt = performance.now();

    setBrightness(startBrightness);
    setHue(startHue);
    setProgress(0);
    setRunning(true);
    setIsOff(false);
    setInterrupted(false);
    setStatus(
      mode === "fado"
        ? "Fade running · paced for this light"
        : "Basic transition running · behavior depends on the light"
    );

    const tick = (now: number) => {
      const rawProgress = clamp((now - startedAt) / demoDuration, 0, 1);
      const eased =
        mode === "fado"
          ? ease(rawProgress, easing, rising)
          : Math.round(rawProgress * 5) / 5;

      setProgress(rawProgress * 100);
      setBrightness(
        startBrightness +
          (scenario.targetBrightness - startBrightness) * eased
      );
      setHue(interpolateHue(startHue, scenario.targetHue, eased));

      if (rawProgress < 1) {
        animationRef.current = requestAnimationFrame(tick);
        return;
      }

      animationRef.current = null;
      setRunning(false);
      setIsOff(scenario.targetBrightness === 0);
      setStatus(
        scenario.targetBrightness === 0
          ? mode === "fado"
            ? `Fade complete · ${scenario.fromBrightness}% safely remembered`
            : "Fade complete · the bulb may remember its last low level"
          : mode === "fado"
            ? "Fade complete · target reached smoothly"
            : "Transition complete"
      );
    };

    animationRef.current = requestAnimationFrame(tick);
  };

  const useWallSwitch = () => {
    cancelAnimation();
    const nextState = getWallSwitchResult({
      isOff,
      mode,
      originalBrightness: scenario.fromBrightness,
    });

    if (!nextState.isOff) {
      setBrightness(nextState.brightness);
      setIsOff(false);
      setHue(scenario.fromHue);
      setRunning(false);
      setInterrupted(false);
      setProgress(0);
      setStatus(
        mode === "fado"
          ? `Restored to ${nextState.brightness}% · the brightness you actually chose`
          : "Back on at 1% · the bulb's last fade level"
      );
      return;
    }

    setBrightness(nextState.brightness);
    setIsOff(true);
    setRunning(false);
    setInterrupted(true);
    setStatus(
      mode === "fado"
        ? "Manual change detected · fade cancelled, your choice wins"
        : "Wall switch sent · the outcome varies by light and transition"
    );
  };

  const copyYaml = async () => {
    const yaml = scenario.yaml.replace("transition: 15", `transition: ${transition}`);
    const result = await copyTextWithFallback({
      text: yaml,
      writeText: navigator.clipboard?.writeText?.bind(navigator.clipboard),
      selectText: () => {
        if (!yamlCodeRef.current) return;
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(yamlCodeRef.current);
        selection?.removeAllRanges();
        selection?.addRange(range);
      },
    });
    setCopyState(result);
    window.setTimeout(() => setCopyState("idle"), 2400);
  };

  const switchLabel =
    isOff
      ? "Turn back on at wall"
      : running
        ? "Press wall switch now"
        : "Turn off at wall";

  const yaml = scenario.yaml.replace("transition: 15", `transition: ${transition}`);

  return (
    <main>
      <nav className="nav" aria-label="Primary navigation">
        <a
          className="brand"
          href="#top"
          aria-label="Fado community demo home"
        >
          <span className="brand-mark">
            <Lightbulb size={19} strokeWidth={2.3} />
          </span>
          <span>Fado demo</span>
        </a>
        <div className="nav-links">
          <a href="#playground">Playground</a>
          <a href="#how">How it works</a>
          <a href={`${import.meta.env.BASE_URL}docs/`}>Docs</a>
          <a
            className="nav-github"
            href="https://github.com/clintongormley/ha-fado"
            target="_blank"
            rel="noreferrer"
          >
            <Github size={17} aria-hidden="true" />
            GitHub
          </a>
        </div>
      </nav>

      <section className="hero-signature" id="top">
        <div className="hero-signature-copy">
          <p className="eyebrow">The Fado moment</p>
          <h1>Smooth fading isn’t smart if it fights the wall switch.</h1>
          <p className="hero-lede">
            Start the fade. Interrupt it like a real person would. Then turn the
            light back on.
          </p>
          <p className="hero-prompt">Three clicks. No setup.</p>
        </div>
        <SignatureDemo />
      </section>

      <section className="playground-section" id="playground">
        <div className="section-heading">
          <div>
            <p className="kicker">Go deeper</p>
            <h2>Tune the fade. Compare the behavior.</h2>
          </div>
          <p>
            Explore brightness, color, timing, easing, and how a basic light
            call behaves without Fado’s coordination layer.
          </p>
        </div>

        <div className="playground-shell">
          <div className="control-column">
            <div
              className="comparison-teaser"
              aria-label="Motion preview: Fado moves smoothly while a basic light call moves in visible steps."
            >
              <div className="comparison-teaser-heading">
                <span>Motion preview</span>
                <small>Watch the difference</small>
              </div>
              <div className="comparison-teaser-row fado-preview">
                <span>With Fado</span>
                <span className="comparison-teaser-rail" aria-hidden="true">
                  <i />
                </span>
                <strong>Smooth</strong>
              </div>
              <div className="comparison-teaser-row basic-preview">
                <span>Basic call</span>
                <span className="comparison-teaser-rail" aria-hidden="true">
                  <i />
                </span>
                <strong>Stepped</strong>
              </div>
            </div>

            <div className="mode-switch" aria-label="Comparison mode">
              <button
                type="button"
                className={mode === "fado" ? "active" : ""}
                onClick={() => chooseMode("fado")}
              >
                With Fado
              </button>
              <button
                type="button"
                className={mode === "basic" ? "active" : ""}
                onClick={() => chooseMode("basic")}
              >
                Basic call
              </button>
            </div>

            <div className="control-block">
              <label>Choose a moment</label>
              <div className="scenario-list">
                {scenarios.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`scenario-button ${
                      scenarioId === item.id ? "selected" : ""
                    }`}
                    onClick={() => chooseScenario(item.id)}
                  >
                    <span className="scenario-icon">
                      {item.id === "bedtime"
                        ? "☾"
                        : item.id === "sunrise"
                          ? "☀"
                          : "●"}
                    </span>
                    <span>
                      <small>{item.eyebrow}</small>
                      <strong>{item.title}</strong>
                    </span>
                    {scenarioId === item.id && (
                      <Check size={17} aria-hidden="true" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            <div className="control-row">
              <div className="field">
                <label htmlFor="transition">Real transition</label>
                <select
                  id="transition"
                  value={transition}
                  onChange={(event) => setTransition(Number(event.target.value))}
                >
                  <option value={5}>5 seconds</option>
                  <option value={15}>15 seconds</option>
                  <option value={30}>30 seconds</option>
                  <option value={300}>5 minutes</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="easing">Easing</label>
                <select
                  id="easing"
                  value={easing}
                  onChange={(event) => setEasing(event.target.value as Easing)}
                  disabled={mode === "basic"}
                >
                  <option value="auto">Auto</option>
                  <option value="linear">Linear</option>
                  <option value="ease_in_out_sine">S-curve</option>
                </select>
              </div>
            </div>

            <button
              className="button button-primary run-button"
              type="button"
              onClick={runDemo}
              disabled={running}
            >
              <Play size={18} fill="currentColor" aria-hidden="true" />
              {running ? "Fade in progress…" : "Play the fade"}
            </button>
          </div>

          <div className="room-column">
            <div className="room-header">
              <div>
                <span className="live-dot" />
                Bedroom
              </div>
              <span>{Math.round(brightness)}%</span>
            </div>

            <BedroomScene
              brightness={brightness}
              hue={hue}
              title={scenario.title}
              description={scenario.description}
            />

            <div className="fade-rail" aria-label="Fade progress">
              <div className="fade-rail-track">
                <span style={{ width: `${progress}%` }} />
              </div>
              <div className="fade-rail-labels">
                <span>{scenario.fromBrightness}%</span>
                <span>{scenario.targetLabel}</span>
              </div>
            </div>

            <div
              className={`status-strip ${interrupted ? "interrupted" : ""}`}
              role="status"
              aria-live="polite"
            >
              <Zap size={17} aria-hidden="true" />
              <span>{status}</span>
            </div>

            <div className="demo-actions">
              <button
                className="button button-wall"
                type="button"
                onClick={useWallSwitch}
              >
                <Hand size={18} aria-hidden="true" />
                {switchLabel}
              </button>
              <button
                className="icon-button"
                type="button"
                onClick={() => resetDemo()}
                aria-label="Reset demo"
                title="Reset demo"
              >
                <RotateCcw size={19} aria-hidden="true" />
              </button>
            </div>

            <p className="simulation-note">
              Interactive simulation. The demo is time-compressed; real timing
              also depends on Home Assistant, your network, and the light.
            </p>
          </div>
        </div>
      </section>

      <section className="why-section" id="how">
        <div className="why-intro">
          <p className="kicker">The tiny layer that changes the feeling</p>
          <h2>Automation can be graceful without taking control away.</h2>
        </div>
        <div className="feature-lines">
          <article>
            <span>01</span>
            <div>
              <h3>Smooth where it matters</h3>
              <p>
                Fado calculates paced steps, applies easing, and uses the
                light’s own native transition support when it genuinely helps.
              </p>
            </div>
          </article>
          <article>
            <span>02</span>
            <div>
              <h3>Human intent comes first</h3>
              <p>
                Touch a wall switch or change the light in the app and Fado
                cancels the fade, clears in-flight steps, and preserves your
                final choice.
              </p>
            </div>
          </article>
          <article>
            <span>03</span>
            <div>
              <h3>Each light gets understood</h3>
              <p>
                The autoconfiguration panel measures practical timing, minimum
                real brightness, and native transition behavior per light.
              </p>
            </div>
          </article>
        </div>
      </section>

      <section className="recipe-section">
        <div className="recipe-copy">
          <div className="recipe-icon">
            <SlidersHorizontal size={24} aria-hidden="true" />
          </div>
          <p className="kicker">Mostly a drop-in replacement</p>
          <h2>One readable action. No lighting degree required.</h2>
          <p>
            Target an entity, area, floor, label, device, or light group. Choose
            the destination and duration. Fado resolves the messy parts.
          </p>
          <a
            className="text-link dark-link"
            href={`${import.meta.env.BASE_URL}docs/actions/fade-lights/`}
            target="_blank"
            rel="noreferrer"
          >
            Explore every option
            <ExternalLink size={15} aria-hidden="true" />
          </a>
        </div>
        <div className="code-window">
          <div className="code-window-header">
            <span>automation.yaml</span>
            <button type="button" onClick={copyYaml}>
              {copyState === "copied" ? (
                <>
                  <Check size={15} aria-hidden="true" /> Copied
                </>
              ) : copyState === "manual" ? (
                <>
                  <Copy size={15} aria-hidden="true" /> Selected · ⌘/Ctrl+C
                </>
              ) : (
                <>
                  <Copy size={15} aria-hidden="true" /> Copy
                </>
              )}
            </button>
          </div>
          <pre>
            <code ref={yamlCodeRef}>{yaml}</code>
          </pre>
        </div>
      </section>

      <section className="cta-section">
        <div>
          <p className="kicker">Available in the default HACS store</p>
          <h2>Make tonight’s fade feel right.</h2>
        </div>
        <div className="cta-actions">
          <a
            className="button button-light"
            href="https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado"
            target="_blank"
            rel="noreferrer"
          >
            Open in HACS
            <ExternalLink size={17} aria-hidden="true" />
          </a>
          <a
            className="button button-outline-light"
            href="https://github.com/clintongormley/ha-fado"
            target="_blank"
            rel="noreferrer"
          >
            <Github size={17} aria-hidden="true" />
            View on GitHub
          </a>
        </div>
      </section>

      <footer>
        <a className="brand" href="#top">
          <span className="brand-mark">
            <Lightbulb size={18} aria-hidden="true" />
          </span>
          Fado demo
        </a>
        <p>
          <strong>Unofficial community demo.</strong> Fado is created and
          maintained by Clinton Gormley. No affiliation, endorsement, or support
          is implied.
        </p>
        <a
          href="https://github.com/clintongormley/ha-fado"
          target="_blank"
          rel="noreferrer"
        >
          Original Fado project
        </a>
      </footer>
    </main>
  );
}
