"use client";

import { ArrowRight, ExternalLink, Hand, Play, Sparkles, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  getSignatureOffPresentation,
  getSignatureStageAfterAction,
  type SignatureStage,
} from "../signature-demo-state.mjs";
import {
  easeSignatureFade,
  SIGNATURE_DEMO_DURATION_MS,
} from "../signature-demo-motion.mjs";
import { BedroomScene } from "./BedroomScene";

type FunnelStep = "start" | "switch" | "restoration" | "hacs_click";
type AnalyticsWindow = Window & {
  dataLayer?: Array<Record<string, string>>;
};

const HACS_URL =
  "https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado";

function trackFunnelStep(step: FunnelStep) {
  window.dispatchEvent(
    new CustomEvent("fado:funnel", {
      detail: { step },
    })
  );
  (window as AnalyticsWindow).dataLayer?.push({
    event: "fado_demo_funnel",
    step,
  });
}

export function SignatureDemo() {
  const [stage, setStage] = useState<SignatureStage>("ready");
  const [brightness, setBrightness] = useState(80);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("Bedroom is on at 80%.");
  const [wasInterrupted, setWasInterrupted] = useState(false);
  const animationRef = useRef<number | null>(null);

  const cancelAnimation = () => {
    if (animationRef.current !== null) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  };

  useEffect(() => {
    return () => cancelAnimation();
  }, []);

  const startFade = () => {
    cancelAnimation();
    const startedAt = performance.now();

    setStage(getSignatureStageAfterAction("ready"));
    setBrightness(80);
    setProgress(0);
    setWasInterrupted(false);
    setStatus("Fado is easing toward off. Use the wall switch now.");
    trackFunnelStep("start");

    const tick = (now: number) => {
      const rawProgress = Math.min(
        (now - startedAt) / SIGNATURE_DEMO_DURATION_MS,
        1
      );
      const easedProgress = easeSignatureFade(rawProgress);

      setProgress(rawProgress * 100);
      setBrightness(80 * (1 - easedProgress));

      if (rawProgress < 1) {
        animationRef.current = requestAnimationFrame(tick);
        return;
      }

      animationRef.current = null;
      setStage("off");
      setBrightness(0);
      setStatus("Bedtime fade complete. Fado remembered 80%.");
    };

    animationRef.current = requestAnimationFrame(tick);
  };

  const useWallSwitch = () => {
    cancelAnimation();
    setStage(getSignatureStageAfterAction("fading"));
    setBrightness(0);
    setWasInterrupted(true);
    setStatus("Fade cancelled. Your choice wins.");
    trackFunnelStep("switch");
  };

  const restoreLight = () => {
    setStage(getSignatureStageAfterAction("off"));
    setBrightness(80);
    setProgress(0);
    setStatus("Back to 80%. Fado remembered.");
    trackFunnelStep("restoration");
  };

  const action =
    stage === "ready" ? (
      <button
        className="button button-primary signature-action"
        type="button"
        onClick={startFade}
        data-funnel-step="start"
      >
        <Play size={18} fill="currentColor" aria-hidden="true" />
        Start bedtime fade
      </button>
    ) : stage === "fading" ? (
      <button
        className="button button-wall signature-action"
        type="button"
        onClick={useWallSwitch}
        data-funnel-step="switch"
      >
        <Hand size={18} aria-hidden="true" />
        Use the wall switch
      </button>
    ) : stage === "off" ? (
      <button
        className="button button-wall signature-action"
        type="button"
        onClick={restoreLight}
        data-funnel-step="restoration"
      >
        <Zap size={18} aria-hidden="true" />
        Turn it back on
      </button>
    ) : (
      <a
        className="button button-primary signature-action"
        href={HACS_URL}
        target="_blank"
        rel="noreferrer"
        onClick={() => trackFunnelStep("hacs_click")}
        data-funnel-step="hacs_click"
      >
        Add Fado to Home Assistant
        <ExternalLink size={17} aria-hidden="true" />
      </a>
    );

  const offPresentation = getSignatureOffPresentation(wasInterrupted);

  const sceneDescription =
    stage === "ready"
      ? "Warm light at 80%. Ready to fade."
      : stage === "fading"
        ? "Easing toward off. Interrupt with the wall switch."
        : stage === "off"
          ? offPresentation.description
          : "Light restored to the remembered 80%.";

  const momentLabel =
    stage === "ready"
      ? "Starts here"
      : stage === "fading"
        ? "Fado is easing"
        : stage === "off"
          ? offPresentation.label
          : "Memory restored";

  return (
    <div
      className={`signature-demo stage-${stage}`}
      aria-label="Interactive Fado demonstration"
    >
      <div className="signature-demo-header">
        <div>
          <span className="live-dot" />
          Live bedroom
        </div>
        <span>{Math.round(brightness)}%</span>
      </div>

      <div className="signature-scene-wrap">
        <BedroomScene
          brightness={brightness}
          hue={38}
          title="Bedtime"
          description={sceneDescription}
          className="signature-room-scene"
        />
        <div className="signature-moment" aria-hidden="true">
          <span>{momentLabel}</span>
          <strong>
            {stage === "off" ? "OFF" : `${Math.round(brightness)}%`}
          </strong>
        </div>
      </div>

      <div className="fade-rail signature-fade-rail" aria-label="Fade progress">
        <div className="fade-rail-track">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="fade-rail-labels">
          <span>80%</span>
          <span>Off</span>
        </div>
      </div>

      <div
        className={`status-strip signature-status ${
          stage === "off" ? "interrupted" : ""
        } ${stage === "restored" ? "restored" : ""}`}
        role="status"
        aria-live="polite"
      >
        {stage === "restored" ? (
          <Sparkles size={17} aria-hidden="true" />
        ) : (
          <Zap size={17} aria-hidden="true" />
        )}
        <span>{status}</span>
      </div>

      <div className="signature-action-row">
        {action}
        <span aria-hidden="true">
          {stage === "ready" && "1 / 3"}
          {stage === "fading" && "2 / 3"}
          {stage === "off" && "3 / 3"}
          {stage === "restored" && <ArrowRight size={18} />}
        </span>
      </div>
    </div>
  );
}
