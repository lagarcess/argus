"use client";

import { Sidebar } from "@/components/Sidebar";
import { TopNav } from "@/components/TopNav";

export default function SettingsPage() {
  return (
    <div className="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen" data-mode="connect">
      <TopNav />
      <div className="flex pt-20">
        <Sidebar />

        <main className="flex-1 md:ml-64 p-8 min-h-[calc(100vh-80px)]">
          {/* Reality Gap Banner */}
          <div className="relative w-full h-32 rounded-xl overflow-hidden mb-12 flex items-center px-12 group bg-surface-container-high border border-outline-variant/20">
            <div className="absolute inset-0 bg-gradient-to-r from-background via-background/60 to-transparent z-10"></div>
            {/* Using a placeholder gradient instead of aida image */}
            <div className="absolute inset-0 w-full h-full bg-gradient-to-br from-primary/10 via-surface to-background opcaity-50"></div>
            <div className="relative z-20">
              <h2 className="font-headline text-3xl font-extrabold tracking-tighter text-on-surface">REALITY GAP APPLIED</h2>
              <p className="text-primary text-xs tracking-[0.3em] font-bold mt-1 uppercase">Backtesting High-Fidelity Protocol Active</p>
            </div>
          </div>

          <div className="max-w-4xl mx-auto space-y-16">
            <div className="space-y-2">
              <h1 className="font-headline text-5xl font-bold tracking-tighter text-on-surface">User Settings</h1>
              <p className="text-on-surface-variant text-sm max-w-lg">
                Manage your account credentials, security layers, and automated notification thresholds for the Argus network.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Profile Section */}
              <section className="md:col-span-12 glass-panel rounded-xl p-8 border border-outline-variant/15 relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[100px] pointer-events-none group-hover:bg-primary/10 transition-colors"></div>
                <div className="flex flex-col md:flex-row items-start md:items-center gap-8 relative z-10">
                  <div className="relative">
                    <div className="w-32 h-32 rounded-full border-2 border-primary bg-surface-variant flex items-center justify-center shadow-[0_0_30px_rgba(153,247,255,0.2)]">
                      <span className="material-symbols-outlined text-6xl text-primary/50">person</span>
                    </div>
                    <button className="absolute bottom-1 right-1 w-10 h-10 rounded-full bg-primary text-on-primary flex items-center justify-center shadow-lg hover:scale-105 transition-transform">
                      <span className="material-symbols-outlined text-sm">edit</span>
                    </button>
                  </div>
                  <div className="flex-1 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-1">
                        <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Account Name</label>
                        <p className="text-xl font-headline font-semibold text-on-surface">Alexander Vance</p>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Account Email</label>
                        <p className="text-xl font-headline font-semibold text-on-surface">vance.alex@argus.io</p>
                      </div>
                    </div>
                    <div className="flex gap-4">
                      <button className="px-6 py-2 rounded-full bg-primary text-on-primary font-headline font-bold text-sm hover:shadow-[0_0_15px_rgba(153,247,255,0.4)] transition-all">Update Profile</button>
                      <button className="px-6 py-2 rounded-full border border-outline-variant text-on-surface-variant font-headline font-bold text-sm hover:bg-surface-container transition-all">Export Data</button>
                    </div>
                  </div>
                </div>
              </section>

              {/* Security Section */}
              <section className="md:col-span-7 glass-panel rounded-xl p-8 border border-outline-variant/15 flex flex-col justify-between">
                <div className="space-y-6">
                  <div className="flex items-center gap-3 mb-6">
                    <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>security</span>
                    <h3 className="font-headline text-xl font-bold tracking-tight">Security Protocol</h3>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl bg-surface-container-low border border-outline-variant/10">
                    <div className="space-y-1">
                      <p className="font-headline font-bold text-on-surface">Change Password</p>
                      <p className="text-xs text-on-surface-variant">Last updated 42 days ago</p>
                    </div>
                    <button className="p-2 rounded-lg bg-surface-container-highest text-primary hover:bg-primary hover:text-on-primary transition-all">
                      <span className="material-symbols-outlined">key</span>
                    </button>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl bg-surface-container-low border border-outline-variant/10">
                    <div className="space-y-1">
                      <p className="font-headline font-bold text-on-surface">Two-Factor Auth</p>
                      <p className="text-xs text-secondary-fixed">Status: Fully Encrypted</p>
                    </div>
                    <div className="w-12 h-6 rounded-full bg-secondary-container/30 border border-secondary-fixed relative cursor-pointer">
                      <div className="absolute right-1 top-1 w-4 h-4 rounded-full bg-secondary-fixed shadow-[0_0_10px_rgba(47,248,1,0.5)]"></div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Notifications Section */}
              <section className="md:col-span-5 glass-panel rounded-xl p-8 border border-outline-variant/15">
                <div className="space-y-6">
                  <div className="flex items-center gap-3 mb-6">
                    <span className="material-symbols-outlined text-primary">notifications</span>
                    <h3 className="font-headline text-xl font-bold tracking-tight">Alert Preferences</h3>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-on-surface-variant">Email Trading Alerts</span>
                      <div className="w-10 h-5 rounded-full bg-primary/20 border border-primary relative cursor-pointer">
                        <div className="absolute right-0.5 top-0.5 w-3.5 h-3.5 rounded-full bg-primary"></div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-on-surface-variant">Push Strategy Success</span>
                      <div className="w-10 h-5 rounded-full bg-primary/20 border border-primary relative cursor-pointer">
                        <div className="absolute right-0.5 top-0.5 w-3.5 h-3.5 rounded-full bg-primary"></div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-on-surface-variant">System Health Reports</span>
                      <div className="w-10 h-5 rounded-full bg-surface-container-highest border border-outline-variant relative cursor-pointer">
                        <div className="absolute left-0.5 top-0.5 w-3.5 h-3.5 rounded-full bg-outline-variant"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            <div className="pt-8 border-t border-outline-variant/10 flex justify-between items-center pb-12">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-secondary-fixed animate-pulse"></span>
                <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant">System Status: Optimal</span>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile nav */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full h-16 bg-[#0e0e10]/80 backdrop-blur-xl border-t border-neutral-800/20 flex justify-around items-center z-50">
        <span className="material-symbols-outlined text-neutral-500">grid_view</span>
        <span className="material-symbols-outlined text-neutral-500">add_box</span>
        <span className="material-symbols-outlined text-cyan-400" style={{ fontVariationSettings: "'FILL' 1" }}>settings</span>
        <span className="material-symbols-outlined text-neutral-500">account_circle</span>
      </nav>
    </div>
  );
}
