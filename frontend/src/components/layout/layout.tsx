import { Outlet } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { Header } from "./header";

export function Layout() {
  return (
    <div className="flex h-screen bg-background text-text-primary font-sans antialiased">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 pb-12">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
