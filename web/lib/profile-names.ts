/**
 * One rule for the two name fields, so the browser and the API cannot disagree.
 *
 * Normalize first, then measure. Bounding the raw value instead put the limit on
 * what the user typed around the name rather than on the name: a leading space
 * in front of a forty-character name is a legal forty-character name, and
 * slicing the raw value to the bound silently dropped its last character on the
 * way past.
 *
 * The backend states the same rule in `src/argus/api/schemas.py`
 * (`PreferredName`), which normalizes in a before-validator so `max_length`
 * measures the trimmed value.
 */

/** Matches the backend's `PREFERRED_NAME_MAX_LENGTH`. */
export const PREFERRED_NAME_MAX_LENGTH = 40;

/**
 * The display-name bound the profile dialog has always enforced.
 *
 * The API does not bound `display_name` at all, so this is a UI-only limit
 * today. It is stated here rather than inline so the asymmetry is visible.
 */
export const DISPLAY_NAME_MAX_LENGTH = 60;

/** What actually gets saved, for any profile name field. */
export function normalizeProfileName(value: string): string {
  return value.trim();
}

/**
 * Length in code points, which is what the bound is stated in.
 *
 * `String.length` counts UTF-16 code units, so every character outside the BMP
 * counts twice: a name of 21 emoji measures 42 here and 21 to `len()` in Python
 * and to `char_length` in Postgres. Measuring in code units made the browser
 * refuse names the API and the database both accept.
 */
export function profileNameLength(value: string): number {
  return Array.from(value).length;
}

/** Measured after normalizing, never before. */
export function profileNameExceeds(value: string, maxLength: number): boolean {
  return profileNameLength(normalizeProfileName(value)) > maxLength;
}
