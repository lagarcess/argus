import { useCallback, useEffect, useState } from "react";
import {
  House,
  Landmark,
  ArrowLeftRight,
  ChartNoAxesCombined,
  Wallet,
  Target,
  SlidersHorizontal,
  ChartPie,
  Coins,
  CreditCard,
  Files,
  Users,
  Settings,
  Headphones,
  Bookmark,
  BadgeCheck,
  BriefcaseBusiness,
} from "lucide-react";
import type { Page } from "./types";

export const destinations = [
  {
    id: "overview",
    es: "Resumen",
    en: "Overview",
    icon: House,
    group: "money",
  },
  {
    id: "accounts",
    es: "Cuentas",
    en: "Accounts",
    icon: Landmark,
    group: "money",
  },
  {
    id: "transactions",
    es: "Movimientos",
    en: "Transactions",
    icon: ArrowLeftRight,
    group: "money",
  },
  {
    id: "spending",
    es: "Gastos",
    en: "Spending",
    icon: ChartNoAxesCombined,
    group: "money",
  },
  {
    id: "budgets",
    es: "Presupuestos",
    en: "Budgets",
    icon: Wallet,
    group: "money",
  },
  { id: "goals", es: "Metas", en: "Goals", icon: Target, group: "plan" },
  {
    id: "scenarios",
    es: "Escenarios",
    en: "Scenarios",
    icon: SlidersHorizontal,
    group: "plan",
  },
  {
    id: "investments",
    es: "Inversiones",
    en: "Investments",
    icon: ChartPie,
    group: "plan",
  },
  {
    id: "deposits",
    es: "Depósitos",
    en: "Deposits",
    icon: Coins,
    group: "plan",
  },
  {
    id: "credit",
    es: "Crédito",
    en: "Credit",
    icon: CreditCard,
    group: "plan",
  },
  {
    id: "tax-estate",
    es: "Impuestos y legado",
    en: "Tax and estate",
    icon: Files,
    group: "plan",
  },
  {
    id: "help",
    es: "Ayuda humana",
    en: "Human help",
    icon: Headphones,
    group: "utility",
  },
  {
    id: "settings",
    es: "Configuración",
    en: "Settings",
    icon: Settings,
    group: "utility",
  },
  {
    id: "household",
    es: "Hogar",
    en: "Household",
    icon: Users,
    group: "household",
  },
  {
    id: "membership",
    es: "Membresía",
    en: "Membership",
    icon: BadgeCheck,
    group: "household",
  },
  {
    id: "employer",
    es: "Beneficios de empresa",
    en: "Employer benefits",
    icon: BriefcaseBusiness,
    group: "household",
  },
  {
    id: "saved",
    es: "Guardados",
    en: "Saved",
    icon: Bookmark,
    group: "household",
  },
] as const;
function currentRoute() {
  const [name, search = ""] = window.location.hash.slice(1).split("?");
  return {
    page: (destinations.some((item) => item.id === name)
      ? name
      : "overview") as Page,
    query: new URLSearchParams(search),
  };
}
export function useNavigation() {
  const [route, setRoute] = useState(currentRoute);
  useEffect(() => {
    const change = () => setRoute(currentRoute());
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  const navigate = useCallback(
    (page: Page, query: Record<string, string> = {}) => {
      const search = new URLSearchParams(query).toString();
      const hash = `#${page}${search ? `?${search}` : ""}`;
      if (window.location.hash === hash) setRoute(currentRoute());
      else window.location.hash = hash;
    },
    [],
  );
  return { ...route, navigate };
}
