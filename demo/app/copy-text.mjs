export async function copyTextWithFallback({
  text,
  writeText,
  selectText,
}) {
  try {
    if (typeof writeText !== "function") {
      throw new Error("Clipboard write is unavailable");
    }
    await writeText(text);
    return "copied";
  } catch {
    selectText();
    return "manual";
  }
}
