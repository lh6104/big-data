import { Search, Mail, Bell } from "lucide-react";

export function TopBar() {
  return (
    <div className="mb-6 flex items-center gap-4">
      <div className="relative flex-1">
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          placeholder="Search roads, segments, hotspots…"
          className="h-12 w-full rounded-full border border-border bg-card pl-11 pr-4 text-sm outline-none placeholder:text-muted-foreground focus:border-primary"
        />
      </div>
      <button className="flex h-11 w-11 items-center justify-center rounded-full bg-card text-foreground hover:bg-secondary">
        <Mail className="h-4 w-4" />
      </button>
      <button className="relative flex h-11 w-11 items-center justify-center rounded-full bg-card text-foreground hover:bg-secondary">
        <Bell className="h-4 w-4" />
        <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-primary" />
      </button>
      <div className="h-8 w-px bg-border" />
      <div className="flex items-center gap-3 pr-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-soft text-sm font-semibold text-accent-foreground">
          OP
        </div>
        <div className="text-sm">
          <div className="font-semibold leading-tight">Operator Hung</div>
          <div className="text-[11px] text-muted-foreground">Traffic Control</div>
        </div>
      </div>
    </div>
  );
}