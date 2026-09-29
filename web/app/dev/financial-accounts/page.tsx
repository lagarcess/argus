import { notFound } from "next/navigation";
import FinancialAccountsClient from "./FinancialAccountsClient";

export const metadata = { title: "Accounts - Argus" };
export const dynamic = "force-dynamic";

export default function FinancialAccountsPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <FinancialAccountsClient />;
}
