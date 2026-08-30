/**
 * Client-side integrity checking for clearance report PDFs.
 *
 * Hashing happens entirely in the browser via the Web Crypto API. The file the
 * user supplies is never uploaded, so a report that has left our control (say,
 * forwarded by email months later) can be checked against the digest recorded
 * at sign-off without handing the document back to the server.
 */

export const VERIFY_STATE = {
  VERIFIED: 'verified',
  MISMATCH: 'mismatch',
  NO_REFERENCE: 'no_reference',
};

const PDF_MAGIC = '%PDF-';

/**
 * True when Web Crypto's digest API is usable.
 *
 * crypto.subtle is exposed only in secure contexts. https and localhost/127.0.0.1
 * qualify, but a plain-http LAN address (e.g. http://192.168.1.5:5173) does not,
 * so this has to be checked rather than assumed.
 */
export function isHashingSupported() {
  return typeof crypto !== 'undefined' && !!crypto?.subtle?.digest;
}

/** Lowercase hex encoding of an ArrayBuffer. */
function toHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

/** SHA-256 of a File or Blob, as a lowercase hex string. */
export async function sha256Hex(file) {
  if (!isHashingSupported()) {
    throw new Error(
      'This browser cannot hash files here. Secure context (https or localhost) required.'
    );
  }
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return toHex(digest);
}

/** Whether the first bytes look like a PDF. Used only to explain a mismatch. */
export async function looksLikePdf(file) {
  try {
    const head = await file.slice(0, PDF_MAGIC.length).text();
    return head === PDF_MAGIC;
  } catch {
    return false;
  }
}

/**
 * Hash a user-supplied file and compare it to the digest recorded at sign-off.
 *
 * Returns { state, actualHash, expectedHash, isPdf }. A missing or blank
 * expectedHash yields NO_REFERENCE — deliberately distinct from MISMATCH,
 * since "we have nothing to compare against" is not evidence of tampering.
 */
export async function verifyReportFile(file, expectedHash) {
  const actualHash = await sha256Hex(file);
  const expected = (expectedHash || '').trim().toLowerCase();

  if (!expected) {
    return {
      state: VERIFY_STATE.NO_REFERENCE,
      actualHash,
      expectedHash: null,
      isPdf: await looksLikePdf(file),
    };
  }

  const matches = actualHash === expected;
  return {
    state: matches ? VERIFY_STATE.VERIFIED : VERIFY_STATE.MISMATCH,
    actualHash,
    expectedHash: expected,
    // Only worth computing for a mismatch, where "you dropped the wrong kind of
    // file" is the most likely explanation.
    isPdf: matches ? true : await looksLikePdf(file),
  };
}
