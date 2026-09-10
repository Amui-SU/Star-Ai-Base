export function normalizeVideoNoteTimeSeconds(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : 0;
}

export function formatVideoNoteTime(value: unknown): string {
  const totalSeconds = normalizeVideoNoteTimeSeconds(value);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const minuteSeconds = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  return hours > 0
    ? `${String(hours).padStart(2, "0")}:${minuteSeconds}`
    : minuteSeconds;
}
