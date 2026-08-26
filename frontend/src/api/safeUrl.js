/**
 * Allow only absolute http(s) URLs for evidence links.
 */
export function isSafeHttpUrl(value) {
  if (typeof value !== 'string') return false;
  const text = value.trim();
  if (!text) return false;
  const lowered = text.toLowerCase();
  if (
    lowered.startsWith('javascript:') ||
    lowered.startsWith('data:') ||
    lowered.startsWith('file:') ||
    lowered.startsWith('vbscript:')
  ) {
    return false;
  }
  try {
    const parsed = new URL(text);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}
