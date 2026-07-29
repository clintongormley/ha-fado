export function getWallSwitchResult({
  isOff,
  mode,
  originalBrightness,
}) {
  if (isOff) {
    return {
      brightness: mode === "fado" ? originalBrightness : 1,
      isOff: false,
    };
  }

  return {
    brightness: 0,
    isOff: true,
  };
}
