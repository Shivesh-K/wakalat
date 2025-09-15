import { AppLayout } from "@/components/layout/app-layout"

export default function ArgumentsPage() {
  return (
    <AppLayout>
      <div className="p-8">
        <h1 className="text-3xl font-bold text-gray-900">Arguments</h1>
        <p className="mt-2 text-gray-600">Generate and manage legal arguments for your cases.</p>

        <div className="mt-8">
          <p className="text-gray-500">Arguments generation coming soon...</p>
        </div>
      </div>
    </AppLayout>
  )
}