"use client";

import { X, ChevronRight, User, LogOut } from "lucide-react";

type SettingsViewProps = {
  onClose: () => void;
  onLogout: () => void;
};

export default function SettingsView({ onClose, onLogout }: SettingsViewProps) {
  return (
    <div className="flex flex-col w-full h-[100dvh] max-w-3xl mx-auto overflow-hidden bg-[#f9f9f9] dark:bg-[#141517] relative font-space">
      {/* Header */}
      <div className="absolute top-0 inset-x-0 h-28 z-30 pointer-events-none backdrop-blur-[8px] bg-[#f5f5f5]/10 dark:bg-[#191c1f]/20 [mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)]" />

      <div className="absolute top-6 inset-x-0 w-full flex justify-center z-[35] pointer-events-none">
        <h1 className="text-[18px] font-medium tracking-tight pointer-events-auto">Settings</h1>
      </div>

      <div className="absolute top-4 right-4 z-[35]">
        <button 
          onClick={onClose} 
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white border border-black/10 dark:border-white/10"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pt-24 pb-32 relative z-10 w-full max-w-md mx-auto">
        <div className="flex flex-col gap-6 w-full">
          
          {/* Profile Section */}
          <button className="flex items-center justify-between p-4 bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[20px] shadow-sm hover:opacity-80 transition-opacity text-left w-full">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-[#f4e8ff] dark:bg-[#342442] flex items-center justify-center border border-black/5 dark:border-white/5 shrink-0">
                <User className="w-6 h-6 text-[#9a66d9] dark:text-[#d3a8fc]" />
              </div>
              <div className="flex flex-col">
                <span className="text-[16px] font-medium text-black dark:text-white">Display Name</span>
                <span className="text-[14px] text-black/50 dark:text-white/50">user-name</span>
                <span className="text-[14px] text-black/50 dark:text-white/50">email@example.com</span>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-black/40 dark:text-white/40" />
          </button>

          {/* Subscription */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">Subscription</span>
            <button className="w-full py-4 px-4 bg-[#f4e8ff]/80 dark:bg-[#342442]/80 border border-[#9a66d9]/20 dark:border-[#d3a8fc]/20 rounded-[16px] shadow-sm hover:opacity-80 transition-opacity text-center flex items-center justify-center">
              <span className="text-[15px] font-medium text-[#7e47be] dark:text-[#e4c4fd]">Try upgrading to Pro for Free</span>
            </button>
          </div>

          {/* App */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">App</span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] shadow-sm overflow-hidden">
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">app language</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <span className="text-[15px] text-black dark:text-white font-medium">appearance</span>
                <div className="flex items-center gap-2">
                  <span className="text-[14px] text-black/40 dark:text-white/40">&lt;system&gt;</span>
                  <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
                </div>
              </button>
            </div>
          </div>

          {/* Data & Information */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">Data & Information</span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] shadow-sm overflow-hidden">
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">archived chats</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">recently deleted</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <span className="text-[15px] text-black dark:text-white font-medium">security</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
            </div>
          </div>

          {/* About */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">About</span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] shadow-sm overflow-hidden">
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">report a bug</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">request a feature</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <span className="text-[15px] text-black dark:text-white font-medium">general feedback</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
            </div>
          </div>

          {/* Log out */}
          <button 
            onClick={onLogout}
            className="w-[140px] mt-2 py-3 px-4 bg-red-400/20 dark:bg-red-500/10 border border-red-500/20 rounded-[12px] shadow-sm hover:opacity-80 transition-opacity text-center flex items-center justify-center gap-2"
          >
            <LogOut className="w-4 h-4 text-red-600 dark:text-red-400" />
            <span className="text-[14px] font-medium text-red-600 dark:text-red-400">Log out</span>
          </button>
          
        </div>
      </div>
    </div>
  );
}
