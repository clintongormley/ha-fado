export function getSignatureStageAfterAction(stage) {
  if (stage === "ready") return "fading";
  if (stage === "fading") return "off";
  if (stage === "off") return "restored";
  return "restored";
}

export function getSignatureOffPresentation(interrupted) {
  if (interrupted) {
    return {
      label: "Manual override",
      description: "Manual switch off. Fade cancelled.",
    };
  }

  return {
    label: "Fade complete",
    description: "Bedtime fade reached off. Fado remembered 80%.",
  };
}
