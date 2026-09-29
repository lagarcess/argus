"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getMe, logoutFromApi } from "@/lib/argus-api";
import { getSupabaseClient } from "@/lib/supabase-client";
import type { UserResponse } from "@/lib/guest-account";
import { createFinancialAccountRequestOwner } from "@/lib/financial-accounts-requests";
import { accountErrorCode, accountErrorStatus, isRetiredAccountRequest } from "./account-form-state";

export function useAccountsSession() {
  const { i18n } = useTranslation();
  const [requests] = useState(() => createFinancialAccountRequestOwner());
  const [profile, setProfile] = useState<UserResponse | null>(null);
  const [identity, setIdentity] = useState<string | null>(null);
  const [epoch, setEpoch] = useState(0);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const identityRef = useRef<string | null>(null);
  const mounted = useRef(false);
  const probe = useRef(0);
  const converting = useRef(false);

  const acceptIdentity = useCallback((nextId: string | null, force = false) => {
    if (identityRef.current === nextId && !force) return;
    requests.setIdentity(null);
    identityRef.current = nextId;
    requests.setIdentity(nextId);
    probe.current += 1;
    setIdentity(nextId);
    setEpoch((value) => value + 1);
    setProfile(null);
    setError(null);
  }, [requests]);

  const retire = useCallback(() => {
    acceptIdentity(null, true);
    setChecking(false);
  }, [acceptIdentity]);

  const verify = useCallback(async (expectedUserId?: string): Promise<UserResponse | null> => {
    const ticket = ++probe.current;
    setChecking(true);
    try {
      const client = getSupabaseClient();
      const session = client ? await client.auth.getSession() : null;
      if (!mounted.current || ticket !== probe.current) return null;
      if (session?.error) throw session.error;
      const nextId = session?.data.session?.user.id ?? null;
      if (expectedUserId !== undefined && nextId !== expectedUserId) return null;
      acceptIdentity(nextId);
      const currentTicket = probe.current;
      if (!nextId) { setChecking(false); return null; }
      const result = await requests.execute(() => getMe(nextId));
      if (!mounted.current || currentTicket !== probe.current) return null;
      if (result.user.id !== nextId) { retire(); return null; }
      setProfile(result);
      setError(null);
      setChecking(false);
      if (i18n.language !== result.user.language) void i18n.changeLanguage(result.user.language);
      return result;
    } catch (failure) {
      if (!mounted.current || isRetiredAccountRequest(failure)) return null;
      if (accountErrorStatus(failure) === 401) retire();
      else { setError(accountErrorCode(failure)); setChecking(false); }
      return null;
    }
  }, [acceptIdentity, i18n, requests, retire]);

  useEffect(() => {
    mounted.current = true;
    let subscription: { unsubscribe(): void } | undefined;
    try {
      const client = getSupabaseClient();
      subscription = client?.auth.onAuthStateChange((_event, session) => {
        acceptIdentity(session?.user.id ?? null);
        // Supabase's callback holds its auth lock. Probe only after it returns.
        if (!converting.current) queueMicrotask(() => { if (mounted.current) void verify(); });
      }).data.subscription;
      void verify();
    } catch (failure) {
      setError(accountErrorCode(failure));
      setChecking(false);
    }
    const onFocus = () => { if (!converting.current) void verify(); };
    window.addEventListener("focus", onFocus);
    return () => {
      mounted.current = false;
      probe.current += 1;
      requests.setIdentity(null);
      identityRef.current = null;
      subscription?.unsubscribe();
      window.removeEventListener("focus", onFocus);
    };
  }, [acceptIdentity, requests, verify]);

  const beginConversion = useCallback(() => { converting.current = true; }, []);
  const finishConversion = useCallback((userId: string | null) => {
    converting.current = false;
    if (!userId) retire();
    else void verify(userId);
  }, [retire, verify]);

  const signOut = useCallback(async () => {
    try {
      const result = await logoutFromApi();
      if (result.revocation === "complete") {
        retire();
        if (result.cookieSync === "failed") setError("logout_cookie_sync_failed");
      } else {
        await verify();
        setError("logout_failed");
      }
    } catch { setError("logout_failed"); }
  }, [retire, verify]);

  return { identity, epoch, profile, checking, error, requests, verify, retire, signOut, beginConversion, finishConversion };
}
