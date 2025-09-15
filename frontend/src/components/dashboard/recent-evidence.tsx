"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useAppSelector } from "@/store/hooks"
import Link from "next/link"

export function RecentEvidence() {
  const evidenceFiles = useAppSelector(state => state.evidence.evidenceFiles)

  const recentEvidence = evidenceFiles
    .filter(e => !e.deletedAt)
    .slice(0, 5)
    .sort((a, b) => new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime())

  const getRelevanceBadgeColor = (score: 'high' | 'medium' | 'low') => {
    switch (score) {
      case 'high':
        return 'bg-red-100 text-red-800 hover:bg-red-100'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100'
      case 'low':
        return 'bg-gray-100 text-gray-800 hover:bg-gray-100'
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Recent Evidence</h3>
        <Button variant="outline" size="sm" asChild>
          <Link href="/upload-evidence">View All</Link>
        </Button>
      </div>

      <div className="space-y-4">
        {recentEvidence.map((evidence) => (
          <div
            key={evidence.evidenceId}
            className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
          >
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h4 className="font-medium text-gray-900">{evidence.filename}</h4>
                <Badge
                  variant="secondary"
                  className={getRelevanceBadgeColor(evidence.relevanceScore)}
                >
                  {evidence.relevanceScore} relevance
                </Badge>
              </div>
              {evidence.description && (
                <p className="text-sm text-gray-600 line-clamp-2">{evidence.description}</p>
              )}
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">
                {new Date(evidence.uploadedAt).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit'
                })}
              </p>
            </div>
          </div>
        ))}

        {recentEvidence.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-500">No evidence files found</p>
            <Button className="mt-4" asChild>
              <Link href="/upload-evidence">Upload Evidence</Link>
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}