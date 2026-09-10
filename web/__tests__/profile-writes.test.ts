import { afterEach, describe, expect, test } from "bun:test";

import type { ApiUser } from "../lib/argus-api";
import {
  readProfile,
  saveProfile,
  saveProfileLanguage,
} from "../lib/profile-writes";

const originalFetch = globalThis.fetch;
const originalMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalMockAuth === undefined) {
    delete process.env.NEXT_PUBLIC_MOCK_AUTH;
  } else {
    process.env.NEXT_PUBLIC_MOCK_AUTH = originalMockAuth;
  }
});

const user = (overrides: Partial<ApiUser> = {}): ApiUser => ({
  id: "user-1",
  email: "a@b.c",
  username: "alex",
  display_name: "Alexandra",
  preferred_name: null,
  language: "es-419",
  locale: "es-419",
  onboarding: {
    completed: false,
    stage: "language_selection",
    language_confirmed: false,
    primary_goal: null,
  },
  ...overrides,
});

type Exchange = { body: unknown; answer: (response: Response) => void };

/** Every request waits for the test to answer it. */
function holdRequests(): Exchange[] {
  process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
  const sent: Exchange[] = [];
  globalThis.fetch = ((_url: string, init?: RequestInit) =>
    new Promise<Response>((answer) => {
      sent.push({
        body: init?.body ? JSON.parse(String(init.body)) : null,
        answer,
      });
    })) as typeof fetch;
  return sent;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const saved = (profile: ApiUser) =>
  json(200, { user: profile, account_kind: "registered" });
const refused = () => json(503, { detail: "Profile store unavailable" });

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function pageLanguage(language: string) {
  const i18n = {
    language,
    async changeLanguage(next?: string) {
      if (next) i18n.language = next;
      return ((key: string) => key) as never;
    },
  };
  return i18n;
}

describe("the profile write path", () => {
  test("a request waits for the one ahead of it, even a refused one", async () => {
    const sent = holdRequests();
    const heard: ApiUser[] = [];

    const first = saveProfile({ display_name: "A" }, (u) => heard.push(u));
    const second = saveProfile({ preferred_name: "B" }, (u) => heard.push(u));
    await settle();
    expect(sent.map((request) => request.body)).toEqual([{ display_name: "A" }]);

    sent[0].answer(refused());
    await expect(first).rejects.toThrow();
    await settle();
    expect(sent.map((request) => request.body)).toEqual([
      { display_name: "A" },
      { preferred_name: "B" },
    ]);

    sent[1].answer(saved(user({ preferred_name: "B" })));
    await second;
    expect(heard.map((u) => u.preferred_name)).toEqual(["B"]);
  });

  test("a read queues behind a pending save", async () => {
    const sent = holdRequests();

    const save = saveProfile({ display_name: "A" }, () => undefined);
    const read = readProfile();
    await settle();
    expect(sent).toHaveLength(1);

    sent[0].answer(saved(user({ display_name: "A" })));
    await save;
    await settle();
    expect(sent).toHaveLength(2);

    sent[1].answer(saved(user({ display_name: "A" })));
    expect((await read).user.display_name).toBe("A");
  });

  test("a refused language is shown, then put back, and nothing is handed on", async () => {
    const sent = holdRequests();
    const i18n = pageLanguage("es-419");
    const heard: ApiUser[] = [];

    const outcome = saveProfileLanguage(i18n, "en", {
      onSaved: (u) => heard.push(u),
    });
    await settle();
    expect(i18n.language).toBe("en");
    expect(sent.map((request) => request.body)).toEqual([
      { language: "en", locale: "en-US" },
    ]);

    sent[0].answer(refused());
    expect(await outcome).toBe(false);
    expect(i18n.language).toBe("es-419");
    expect(heard).toEqual([]);
  });

  test("a saved language stays and the saved profile is handed on", async () => {
    const sent = holdRequests();
    const i18n = pageLanguage("es-419");
    const heard: ApiUser[] = [];

    const outcome = saveProfileLanguage(i18n, "en", {
      onSaved: (u) => heard.push(u),
    });
    await settle();
    sent[0].answer(saved(user({ language: "en", locale: "en-US" })));

    expect(await outcome).toBe(true);
    expect(i18n.language).toBe("en");
    expect(heard.map((u) => u.language)).toEqual(["en"]);
  });
});
