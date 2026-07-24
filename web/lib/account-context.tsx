"use client";

import { createContext, useContext } from "react";
import type { UserResponse } from "./guest-account";

const AccountContext = createContext<UserResponse | null>(null);

export function AccountProvider({
  account,
  children,
}: {
  account: UserResponse | null;
  children: React.ReactNode;
}) {
  return (
    <AccountContext.Provider value={account}>
      {children}
    </AccountContext.Provider>
  );
}

export function useAccount() {
  return useContext(AccountContext);
}
