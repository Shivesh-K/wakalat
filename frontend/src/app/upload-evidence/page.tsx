"use client"

import { AppLayout } from "@/components/layout/app-layout"
import { FileDropzone } from "@/components/upload/file-dropzone"
import { useAppDispatch } from "@/store/hooks"
import { addEvidenceFile } from "@/store/slices/evidenceSlice"

export default function UploadEvidencePage() {
  const dispatch = useAppDispatch()

  const handleFilesSelected = (files: FileList) => {
    Array.from(files).forEach((file) => {
      // Create evidence file object
      const evidenceFile = {
        evidenceId: Date.now().toString() + Math.random().toString(36),
        caseId: '1', // Default to first case for now
        filename: file.name,
        uploadedAt: new Date().toISOString(),
        relevanceScore: 'medium' as const,
        description: `Uploaded file: ${file.name}`
      }

      // Add to store
      dispatch(addEvidenceFile(evidenceFile))
    })

    // Show success message or redirect
    console.log(`Uploaded ${files.length} file(s)`)
  }

  return (
    <AppLayout>
      <div className="p-8 max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Upload Evidence</h1>
          <p className="mt-2 text-gray-600">
            Upload legal documents for AI-powered analysis and case preparation.
          </p>
        </div>

        <FileDropzone onFilesSelected={handleFilesSelected} />
      </div>
    </AppLayout>
  )
}