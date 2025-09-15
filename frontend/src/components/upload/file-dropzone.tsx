"use client"

import { useState, useCallback } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Upload } from "lucide-react"

interface FileDropzoneProps {
  onFilesSelected: (files: FileList) => void
}

export function FileDropzone({ onFilesSelected }: FileDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesSelected(e.dataTransfer.files)
    }
  }, [onFilesSelected])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(e.target.files)
    }
  }, [onFilesSelected])

  const handleBrowseClick = () => {
    const input = document.getElementById('file-input') as HTMLInputElement
    input?.click()
  }

  return (
    <Card
      className={`p-12 text-center border-2 border-dashed transition-colors ${
        isDragOver
          ? 'border-orange-500 bg-orange-50'
          : 'border-gray-300 hover:border-gray-400'
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="flex flex-col items-center space-y-6">
        <div className="p-4 bg-gray-100 rounded-lg">
          <Upload className="h-12 w-12 text-gray-400" />
        </div>

        <div className="space-y-2">
          <h3 className="text-xl font-semibold text-gray-700">Upload Legal Documents</h3>
          <p className="text-gray-500">Drag and drop files here, or click to browse</p>
        </div>

        <Button
          onClick={handleBrowseClick}
          className="bg-orange-500 hover:bg-orange-600 text-white px-8 py-3"
        >
          Browse Files
        </Button>

        <p className="text-sm text-gray-500">
          Supported formats: PDF, Word, Text files (Max 10MB each)
        </p>
      </div>

      <input
        id="file-input"
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt"
        onChange={handleFileSelect}
        className="hidden"
      />
    </Card>
  )
}