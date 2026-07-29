export const SIGNATURE_DEMO_DURATION_MS = 11000;

export function easeSignatureFade(progress) {
  const clampedProgress = Math.min(Math.max(progress, 0), 1);
  if (clampedProgress === 0 || clampedProgress === 1) {
    return clampedProgress;
  }
  return -(Math.cos(Math.PI * clampedProgress) - 1) / 2;
}
