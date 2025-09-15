"use client"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Upload,
  BarChart3,
  MessageSquare,
  Search,
  Download,
  Settings,
  LogOut,
  Scale
} from "lucide-react"

interface SidebarProps {
  className?: string
}

const navigationItems = [
  {
    name: "Dashboard",
    icon: LayoutDashboard,
    href: "/dashboard"
  },
  {
    name: "Upload Evidence",
    icon: Upload,
    href: "/upload-evidence"
  },
  {
    name: "Analysis",
    icon: BarChart3,
    href: "/analysis"
  },
  {
    name: "Arguments",
    icon: MessageSquare,
    href: "/arguments"
  },
  {
    name: "Case Research",
    icon: Search,
    href: "/case-research"
  },
  {
    name: "Export",
    icon: Download,
    href: "/export"
  }
]

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname()
  return (
    <div className={cn("flex h-full w-64 flex-col bg-slate-800 text-white", className)}>
      {/* Header */}
      <div className="flex items-center gap-3 p-6 border-b border-slate-700">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-orange-500">
          <Scale className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-semibold">Wakalat AI</h1>
          <p className="text-sm text-slate-400">Legal Analysis</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navigationItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href
          return (
            <Button
              key={item.name}
              variant="ghost"
              className={cn(
                "w-full justify-start gap-3 text-left font-normal",
                isActive
                  ? "bg-orange-500 text-white hover:bg-orange-600"
                  : "text-slate-300 hover:bg-slate-700 hover:text-white"
              )}
              asChild
            >
              <Link href={item.href}>
                <Icon className="h-5 w-5" />
                {item.name}
              </Link>
            </Button>
          )
        })}
      </nav>

      {/* User Section */}
      <div className="border-t border-slate-700 p-4">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-500">
            <span className="text-sm font-medium">SM</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">Sarah Mitchell</p>
            <p className="text-xs text-slate-400 truncate">Mitchell & Associates</p>
          </div>
        </div>

        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-slate-300 hover:bg-slate-700 hover:text-white"
            size="sm"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-slate-300 hover:bg-slate-700 hover:text-white"
            size="sm"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </Button>
        </div>
      </div>
    </div>
  )
}