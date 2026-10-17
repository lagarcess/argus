"use client";

import { useState, type MouseEvent } from "react";
import { House, PanelLeft, Search, Target, UserRound, Wallet } from "lucide-react";
import { ArgusLogo } from "@/components/ArgusLogo";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import { Tooltip } from "@/components/ui/Tooltip";
import { type PreviewAudience, type PreviewCopy, type PreviewView } from "./preview-content";
import styles from "./ecosystem-preview.module.css";

const DESTINATIONS = ["home", "accounts", "argus", "plan", "search"] as const;
const ICONS = { home: House, accounts: Wallet, argus: ArgusLogo, plan: Target, search: Search };

export default function PreviewNavigation({ copy, view, audience, href, onNavigate }: {
  copy: PreviewCopy; view: PreviewView; audience: PreviewAudience;
  href: (view: PreviewView) => string;
  onNavigate: (event: MouseEvent<HTMLAnchorElement>, view: PreviewView) => void;
}) {
  const { isBelowTablet, isBelowDesktop } = useResponsiveLayout();
  const [expandedChoice, setExpandedChoice] = useState<boolean | null>(null);
  const expanded = expandedChoice ?? !isBelowDesktop;
  const toggleLabel = expanded ? copy.collapseNavigation : copy.expandNavigation;

  return <aside className={`${styles.rail} ${expanded ? styles.railExpanded : styles.railCollapsed}`} data-testid="preview-rail" data-expanded={expanded}>
    <div className={styles.railHeader}>
      <Tooltip content={toggleLabel} side="right" delay={150}>
        <button type="button" className={styles.railToggle} aria-label={toggleLabel} aria-expanded={expanded} aria-controls="preview-primary-nav" onClick={() => setExpandedChoice(!expanded)}><PanelLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>
      </Tooltip>
      <span className={styles.brand}>argus</span>
    </div>
    <nav id="preview-primary-nav" className={styles.primaryNav} aria-label={copy.primaryNav}>
      {DESTINATIONS.map((destination) => {
        const Icon = ICONS[destination];
        const link = <a href={href(destination)} onClick={(event) => onNavigate(event, destination)} aria-label={copy[destination]} aria-current={view === destination ? "page" : undefined}>
          <span className={styles.navIcon}><Icon aria-hidden="true" /></span><span className={styles.navLabel}>{copy[destination]}</span>
        </a>;
        return !expanded && !isBelowTablet ? <Tooltip key={destination} content={copy[destination]} side="right" delay={150}>{link}</Tooltip> : <span className={styles.navItem} key={destination}>{link}</span>;
      })}
    </nav>
    <div className={styles.railFoot} aria-label={audience === "guest" ? copy.guest : copy.sampleWorkspace}>
      <span className={styles.workspaceMark}><UserRound size={18} aria-hidden="true" /></span>
      <p>{audience === "guest" ? copy.guest : copy.sampleWorkspace}<small>{copy.localOnly}</small></p>
    </div>
  </aside>;
}
