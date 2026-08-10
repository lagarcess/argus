/**
 * One rule for both name fields: trim, then measure in code points.
 * `PreferredName` in `src/argus/api/schemas.py` states the same rule.
 */

/** Matches the backend's `PREFERRED_NAME_MAX_LENGTH`. */
export const PREFERRED_NAME_MAX_LENGTH = 40;

/** UI-only: the API does not bound `display_name`. */
export const DISPLAY_NAME_MAX_LENGTH = 60;

/** What actually gets saved. */
export function normalizeProfileName(value: string): string {
  return value.trim();
}

/**
 * Code points, not UTF-16 code units, so this agrees with Python `len()` and
 * Postgres `char_length`.
 */
export function profileNameLength(value: string): number {
  return Array.from(value).length;
}

/** Measured after normalizing, never before. */
export function profileNameExceeds(value: string, maxLength: number): boolean {
  return profileNameLength(normalizeProfileName(value)) > maxLength;
}
