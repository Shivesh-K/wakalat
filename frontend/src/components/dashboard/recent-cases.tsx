"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAppSelector } from "@/store/hooks"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"

export function RecentCases() {
  const cases = useAppSelector(state => state.cases.cases)

  const recentCases = cases
    .filter(c => !c.deletedAt)
    .slice(0, 5)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Recent Cases</h3>
        <Button variant="outline" size="sm" asChild>
          <Link href="/cases">View All</Link>
        </Button>
      </div>

      <div className="space-y-4">
        {recentCases.map((case_) => (
          <div
            key={case_.caseId}
            className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
          >
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <h4 className="font-medium text-gray-900">{case_.title}</h4>
                <Badge
                  variant={case_.status === 'active' ? 'default' : 'secondary'}
                  className={
                    case_.status === 'active'
                      ? 'bg-green-100 text-green-800 hover:bg-green-100'
                      : ''
                  }
                >
                  {case_.status}
                </Badge>
              </div>
              <p className="text-sm text-gray-600">{case_.client}</p>
              <p className="text-xs text-gray-500">{case_.caseType}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">
                {new Date(case_.updatedAt).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit'
                })}
              </p>
            </div>
          </div>
        ))}

        {recentCases.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-500">No cases found</p>
            <Button className="mt-4" asChild>
              <Link href="/cases/new">Create Your First Case</Link>
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}