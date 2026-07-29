export type CopyResult = "copied" | "manual";

export function copyTextWithFallback(input: {
  text: string;
  writeText?: (text: string) => Promise<void>;
  selectText: () => void;
}): Promise<CopyResult>;
