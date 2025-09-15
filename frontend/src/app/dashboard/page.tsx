import { AppLayout } from "@/components/layout/app-layout"
import { Button } from "@/components/ui/button"
import { StatsCards } from "@/components/dashboard/stats-cards"
import { RecentCases } from "@/components/dashboard/recent-cases"
import { RecentEvidence } from "@/components/dashboard/recent-evidence"
import { Plus } from "lucide-react"
import Link from "next/link"

export default function DashboardPage() {
  return (
    <AppLayout>
      <div className="p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p className="mt-2 text-gray-600">Welcome back, Sarah. Here's what's happening with your cases.</p>
          </div>
          <Button className="bg-orange-500 hover:bg-orange-600" asChild>
            <Link href="/upload-evidence">
              <Plus className="h-4 w-4 mr-2" />
              New Case
            </Link>
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="mb-8">
          <StatsCards />
        </div>

        {/* Recent Sections */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <RecentCases />
          <RecentEvidence />
        </div>
      </div>
    </AppLayout>
  )
}