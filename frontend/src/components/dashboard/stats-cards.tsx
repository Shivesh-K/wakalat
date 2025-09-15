"use client"

import { Card } from "@/components/ui/card"
import { useAppSelector } from "@/store/hooks"
import {
  Briefcase,
  FileText,
  MessageSquare,
  Search
} from "lucide-react"

interface StatCardProps {
  title: string
  value: number
  icon: React.ComponentType<{ className?: string }>
  iconColor: string
}

function StatCard({ title, value, icon: Icon, iconColor }: StatCardProps) {
  return (
    <Card className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${iconColor}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </Card>
  )
}

export function StatsCards() {
  const cases = useAppSelector(state => state.cases.cases)
  const evidenceFiles = useAppSelector(state => state.evidence.evidenceFiles)
  const argumentsList = useAppSelector(state => state.arguments.arguments)
  const queries = useAppSelector(state => state.research.queries)

  const activeCases = cases.filter(c => c.status === 'active' && !c.deletedAt).length
  const totalEvidenceFiles = evidenceFiles.filter(e => !e.deletedAt).length
  const totalArguments = argumentsList.filter(a => !a.deletedAt).length
  const totalResearchQueries = queries.filter(q => !q.deletedAt).length

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        title="Active Cases"
        value={activeCases}
        icon={Briefcase}
        iconColor="bg-blue-500"
      />
      <StatCard
        title="Evidence Files"
        value={totalEvidenceFiles}
        icon={FileText}
        iconColor="bg-green-500"
      />
      <StatCard
        title="Arguments Generated"
        value={totalArguments}
        icon={MessageSquare}
        iconColor="bg-purple-500"
      />
      <StatCard
        title="Research Queries"
        value={totalResearchQueries}
        icon={Search}
        iconColor="bg-orange-500"
      />
    </div>
  )
}