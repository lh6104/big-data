import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Toaster } from "sonner";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { TopBar } from "@/components/layout/TopBar";

export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

function AppLayout() {
  return (
    <div className="min-h-screen bg-background p-4">
      <div className="flex gap-4">
        <AppSidebar />
        <main className="flex-1 min-w-0">
          <TopBar />
          <Outlet />
        </main>
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}