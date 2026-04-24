"use client";

import { useEffect, useState } from "react";
import { Folder, Menu, Plus, Search, Settings } from "lucide-react";

import { listHistory } from "@/lib/argus-api";

type CollectionItem = {
  id: string;
  title: string;
  subtitle: string;
  pinned: boolean;
};

type CollectionsViewProps = {
  onMenuClick: () => void;
  onSettingsClick?: () => void;
};

export default function CollectionsView({
  onMenuClick,
  onSettingsClick,
}: CollectionsViewProps) {
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [searchText, setSearchText] = useState("");

  useEffect(() => {
    let cancelled = false;
    listHistory()
      .then((history) => {
        if (cancelled) return;
        const items = history.items
          .filter((item) => item.type === "collection")
          .map((item) => ({
            id: item.id,
            title: item.title,
            subtitle: item.subtitle,
            pinned: item.pinned,
          }));
        setCollections(items);
      })
      .catch(() => setCollections([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleCollections = collections.filter((collection) =>
    collection.title.toLowerCase().includes(searchText.toLowerCase()),
  );

  return (
    <div className="flex h-[100dvh] w-full max-w-3xl flex-col overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white">
      <div className="flex h-16 shrink-0 items-center justify-between px-4">
        <button
          type="button"
          onClick={onMenuClick}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-black/10 transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-[18px] font-medium tracking-tight">Collections</h1>
        <button
          type="button"
          className="flex h-11 w-11 items-center justify-center rounded-full border border-black/10 transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
          aria-label="Create collection"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>

      <div className="px-5 pb-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-black/40 dark:text-white/40" />
          <input
            type="text"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search collections"
            className="h-[52px] w-full rounded-full border border-black/10 bg-white pl-12 pr-5 text-[16px] outline-none transition-colors focus:ring-2 focus:ring-black/10 dark:border-white/10 dark:bg-[#1f2225] dark:focus:ring-white/10"
          />
        </div>
      </div>

      <div className="argus-scrollbar flex-1 overflow-y-auto px-5 pb-28">
        {visibleCollections.length === 0 ? (
          <div className="mt-16 flex flex-col items-center gap-3 text-center text-black/55 dark:text-white/55">
            <Folder className="h-8 w-8" />
            <p className="max-w-sm text-[15px] leading-6">
              Collections will appear here when you save strategies from a chat.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {visibleCollections.map((collection) => (
              <article
                key={collection.id}
                className="rounded-[20px] border border-black/10 bg-white p-5 dark:border-white/10 dark:bg-[#1f2225]"
              >
                <h2 className="text-[17px] font-medium tracking-tight">
                  {collection.title}
                </h2>
                <p className="mt-1 text-[13px] text-black/50 dark:text-white/50">
                  {collection.subtitle}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="pointer-events-none absolute bottom-6 inset-x-0 px-4">
        <button
          type="button"
          onClick={onSettingsClick}
          className="pointer-events-auto flex h-[52px] w-[52px] items-center justify-center rounded-full border border-black/10 bg-white/70 backdrop-blur-xl transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/70 dark:hover:bg-white/5"
          aria-label="Open settings"
        >
          <Settings className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
