"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Avatar, AvatarFallback, AvatarImage } from "@radix-ui/react-avatar";
import { BarChart3, FolderGit2, Menu, Settings, ShieldCheck } from "lucide-react";
import { useState } from "react";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/reviews", label: "Reviews", icon: ShieldCheck },
  { href: "/repositories", label: "Repositories", icon: FolderGit2 },
  { href: "/settings", label: "Settings", icon: Settings }
];

export default function Sidebar(): JSX.Element {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <aside className="border-r border-border bg-card">
      <button className="m-3 inline-flex rounded-md border border-border p-2 md:hidden" onClick={() => setOpen((v) => !v)}>
        <Menu className="h-4 w-4" />
      </button>
      <div className={`${open ? "block" : "hidden"} md:block`}>
        <div className="p-4 text-xl font-semibold">CodeSentinel AI</div>
        <nav className="space-y-1 px-3">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} className="block">
                <motion.div
                  whileHover={{ x: 2 }}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
                    active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </motion.div>
              </Link>
            );
          })}
        </nav>
        <div className="mt-8 border-t border-border p-4">
          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8 overflow-hidden rounded-full border border-border">
              <AvatarImage src="https://avatars.githubusercontent.com/u/1?v=4" alt="User avatar" />
              <AvatarFallback>CS</AvatarFallback>
            </Avatar>
            <div>
              <p className="text-sm font-medium">Developer</p>
              <p className="text-xs text-muted-foreground">@codesentinel</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
