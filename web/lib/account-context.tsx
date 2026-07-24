"use client";

import { createContext, useContext } from "react";
import type { UserResponse } from "./guest-account";

const AccountContext = createContext<UserResponse | null>(null);
const AccountRefreshContext = createContext<
  () => Promise<UserResponse | null>
>(async () => null);

export function AccountProvider({
  account,
  refreshAccount = async () => account,
  children,
}: {
  account: UserResponse | null;
  refreshAccount?: () => Promise<UserResponse | null>;
  children: React.ReactNode;
}) {
  return (
    <AccountRefreshContext.Provider value={refreshAccount}>
      <AccountContext.Provider value={account}>
        {children}
      </AccountContext.Provider>
    </AccountRefreshContext.Provider>
  );
}

export function useAccount() {
  return useContext(AccountContext);
}

export function useAccountRefresh() {
  return useContext(AccountRefreshContext);
}
