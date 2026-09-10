import type { i18n as I18n } from "i18next";

import { getMe, patchMe, type ApiUser, type ProfilePatch } from "./argus-api";
import {
  localeForLanguage,
  normalizeEnabledLanguage,
  type ArgusLanguage,
} from "./language-features";

/*
 * The one way a profile field reaches the server.
 *
 * Every read and write of the profile queues here, one at a time for the whole
 * tab. `PATCH /me` rewrites the row from a read, so two in flight can undo each
 * other on the server, and a response that lands late replaces a newer copy.
 */
let profileRequestChain: Promise<unknown> = Promise.resolve();

export function serializeProfileRequest<T>(
  request: () => Promise<T>,
): Promise<T> {
  const queued = profileRequestChain.then(request, request);
  profileRequestChain = queued.then(
    () => undefined,
    () => undefined,
  );
  return queued;
}

export function readProfile() {
  return serializeProfileRequest(() => getMe());
}

/** Rejects when the account did not take the patch; `onSaved` hears every save that did. */
export async function saveProfile(
  patch: ProfilePatch,
  onSaved: (user: ApiUser) => void,
): Promise<void> {
  const { user } = await serializeProfileRequest(() => patchMe(patch));
  onSaved(user);
}

type LanguageTarget = Pick<I18n, "language" | "changeLanguage">;

/**
 * Shows the language at once and, if the account refuses it, puts back the
 * language the page showed. Resolves with whether the account now holds it.
 */
export async function saveProfileLanguage(
  i18n: LanguageTarget,
  code: string,
  {
    onShown,
    onSaved,
  }: {
    onShown?: (language: ArgusLanguage) => void;
    onSaved: (user: ApiUser) => void;
  },
): Promise<boolean> {
  const shownLanguage = i18n.language;
  const language = normalizeEnabledLanguage(code);
  await i18n.changeLanguage(language);
  onShown?.(language);
  try {
    await saveProfile(
      { language, locale: localeForLanguage(language) },
      onSaved,
    );
    return true;
  } catch (error) {
    console.error("Failed to update language", error);
    await i18n.changeLanguage(shownLanguage);
    onShown?.(normalizeEnabledLanguage(shownLanguage));
    return false;
  }
}
