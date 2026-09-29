"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getFinancialAccount, listFinancialAccounts, type FinancialAccount } from "@/lib/financial-accounts-api";
import { createFinancialAccountRequestOwner } from "@/lib/financial-accounts-requests";
import { accountErrorCode, accountErrorStatus, isRetiredAccountRequest } from "./account-form-state";

export type AccountRequestOwner = ReturnType<typeof createFinancialAccountRequestOwner>;

export function useAccountRecords(userId: string, selectedId: string | null, requests: AccountRequestOwner, retire: () => void) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [detail, setDetail] = useState<FinancialAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const listTicket = useRef(0);
  const detailTicket = useRef(0);

  const handleFailure = useCallback((failure: unknown) => {
    if (accountErrorStatus(failure) === 401 || (failure instanceof Error && failure.name === "ChatAccountChangedError")) retire();
    return isRetiredAccountRequest(failure) || accountErrorStatus(failure) === 401;
  }, [retire]);

  const refresh = useCallback(async () => {
    const ticket = ++listTicket.current;
    setLoading(true);
    try {
      const result = await requests.execute((signal) => listFinancialAccounts(userId, signal));
      if (ticket !== listTicket.current) return;
      setAccounts(result);
      setError(null);
    } catch (failure) {
      if (ticket === listTicket.current && !handleFailure(failure)) setError(accountErrorCode(failure));
    } finally { if (ticket === listTicket.current) setLoading(false); }
  }, [handleFailure, requests, userId]);

  const readCurrent = useCallback((id: string) => requests.execute((signal) => getFinancialAccount(userId, id, signal)), [requests, userId]);

  const accept = useCallback((account: FinancialAccount) => {
    listTicket.current += 1;
    detailTicket.current += 1;
    setLoading(false);
    setDetailLoading(false);
    setAccounts((existing) => existing.some((item) => item.id === account.id)
      ? existing.map((item) => item.id === account.id ? account : item)
      : [...existing, account]);
    setDetail(account);
    setDetailError(null);
  }, []);

  useEffect(() => {
    void refresh();
    return () => { listTicket.current += 1; };
  }, [refresh]);

  useEffect(() => {
    const ticket = ++detailTicket.current;
    if (!selectedId) return;
    setDetailLoading(true);
    setDetailError(null);
    void readCurrent(selectedId).then((account) => {
      if (ticket === detailTicket.current) setDetail(account);
    }).catch((failure: unknown) => {
      if (ticket === detailTicket.current && !handleFailure(failure)) setDetailError(accountErrorCode(failure));
    }).finally(() => { if (ticket === detailTicket.current) setDetailLoading(false); });
    return () => { detailTicket.current += 1; };
  }, [handleFailure, readCurrent, selectedId]);

  return { accounts, detail: detail?.id === selectedId ? detail : null, loading, detailLoading, error, detailError, refresh, readCurrent, accept, handleFailure };
}
