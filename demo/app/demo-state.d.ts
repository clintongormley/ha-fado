export type DemoMode = "fado" | "basic";

export function getWallSwitchResult(input: {
  isOff: boolean;
  mode: DemoMode;
  originalBrightness: number;
}): {
  brightness: number;
  isOff: boolean;
};
