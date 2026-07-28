import type { CSSProperties } from "react";

type BedroomSceneProps = {
  brightness: number;
  hue: number;
  title: string;
  description: string;
  className?: string;
};

export function BedroomScene({
  brightness,
  hue,
  title,
  description,
  className = "",
}: BedroomSceneProps) {
  const lampStyle = {
    "--lamp-brightness": `${Math.max(0.02, brightness / 100)}`,
    "--lamp-hue": `${hue}`,
    "--room-lightness": `${12 + brightness * 0.24}%`,
    "--glow-opacity": `${Math.max(0.02, brightness / 100) * 0.34}`,
    "--lamp-opacity": `${0.13 + Math.max(0.02, brightness / 100) * 0.87}`,
    "--lamp-scale": `${0.58 + Math.max(0.02, brightness / 100) * 0.42}`,
  } as CSSProperties;

  return (
    <div className={`room-scene ${className}`.trim()} style={lampStyle}>
      <div className="window">
        <span />
        <span />
      </div>
      <div className="wall-picture">
        <span />
      </div>
      <div className="lamp">
        <div className="lamp-glow" />
        <div className="lamp-shade" />
        <div className="lamp-stem" />
        <div className="lamp-base" />
      </div>
      <div className="bed">
        <div className="pillow" />
        <div className="blanket" />
      </div>
      <div className="side-table" />
      <div className="scene-caption">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
    </div>
  );
}
