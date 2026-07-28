export type SignatureStage = "ready" | "fading" | "off" | "restored";

export function getSignatureStageAfterAction(
  stage: SignatureStage
): SignatureStage;

export function getSignatureOffPresentation(interrupted: boolean): {
  label: string;
  description: string;
};
