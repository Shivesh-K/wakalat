"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { AppLayout } from "@/components/layout/app-layout"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { FileDropzone } from "@/components/upload/file-dropzone"
import { useAppDispatch } from "@/store/hooks"
import { addCase } from "@/store/slices/casesSlice"
import { addEvidenceFile } from "@/store/slices/evidenceSlice"
import { Badge } from "@/components/ui/badge"
import { X, Sparkles } from "lucide-react"

interface UploadedFile {
  file: File
  id: string
}

interface AISuggestions {
  caseTitle?: string
  clientName?: string
  caseType?: string
  description?: string
  confidence: number
}

const caseTypes = [
  "Criminal Defense",
  "Personal Injury",
  "Contract Dispute",
  "Estate Planning",
  "Family Law",
  "Employment Law",
  "Real Estate",
  "Business Law",
  "Immigration",
  "Bankruptcy"
]

export default function NewCasePage() {
  const router = useRouter()
  const dispatch = useAppDispatch()

  // Form state
  const [caseTitle, setCaseTitle] = useState("")
  const [clientName, setClientName] = useState("")
  const [caseType, setCaseType] = useState("")
  const [description, setDescription] = useState("")

  // Evidence state
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])

  // AI suggestions state
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestions | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  // Simulate AI analysis of uploaded documents
  const analyzeDocuments = async (files: UploadedFile[]) => {
    setIsAnalyzing(true)

    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 2000))

    // Mock AI suggestions based on file names
    const fileNames = files.map(f => f.file.name.toLowerCase()).join(" ")

    let suggestions: AISuggestions = { confidence: 85 }

    if (fileNames.includes("police") || fileNames.includes("arrest")) {
      suggestions = {
        caseTitle: "People v. Criminal Defense Matter",
        clientName: "Defendant",
        caseType: "Criminal Defense",
        description: "Criminal defense matter involving potential charges. Evidence includes police reports and related documentation.",
        confidence: 90
      }
    } else if (fileNames.includes("contract") || fileNames.includes("agreement")) {
      suggestions = {
        caseTitle: "Contract Dispute Case",
        clientName: "Contract Party",
        caseType: "Contract Dispute",
        description: "Contract-related dispute requiring legal analysis and potential litigation support.",
        confidence: 88
      }
    } else if (fileNames.includes("accident") || fileNames.includes("injury")) {
      suggestions = {
        caseTitle: "Personal Injury Claim",
        clientName: "Injured Party",
        caseType: "Personal Injury",
        description: "Personal injury matter involving accident and potential damages claim.",
        confidence: 92
      }
    } else {
      suggestions = {
        caseTitle: "Legal Matter",
        clientName: "Client",
        caseType: "Business Law",
        description: "Legal matter requiring analysis and case preparation.",
        confidence: 75
      }
    }

    setAiSuggestions(suggestions)
    setIsAnalyzing(false)
  }

  const handleFilesSelected = (files: FileList) => {
    const newFiles = Array.from(files).map(file => ({
      file,
      id: Date.now().toString() + Math.random().toString(36)
    }))

    const updatedFiles = [...uploadedFiles, ...newFiles]
    setUploadedFiles(updatedFiles)

    // Trigger AI analysis if we have files
    if (updatedFiles.length > 0) {
      analyzeDocuments(updatedFiles)
    }
  }

  const removeFile = (fileId: string) => {
    const updatedFiles = uploadedFiles.filter(f => f.id !== fileId)
    setUploadedFiles(updatedFiles)

    if (updatedFiles.length === 0) {
      setAiSuggestions(null)
    }
  }

  const applySuggestion = (field: keyof AISuggestions, value: string) => {
    switch (field) {
      case 'caseTitle':
        setCaseTitle(value)
        break
      case 'clientName':
        setClientName(value)
        break
      case 'caseType':
        setCaseType(value)
        break
      case 'description':
        setDescription(value)
        break
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Create new case
    const newCase = {
      caseId: Date.now().toString(),
      title: caseTitle,
      client: clientName,
      caseType: caseType,
      status: 'active' as const,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }

    dispatch(addCase(newCase))

    // Add evidence files to store
    uploadedFiles.forEach(({ file }) => {
      const evidenceFile = {
        evidenceId: Date.now().toString() + Math.random().toString(36),
        caseId: newCase.caseId,
        filename: file.name,
        uploadedAt: new Date().toISOString(),
        relevanceScore: 'high' as const,
        description: `Evidence file for ${caseTitle}`
      }
      dispatch(addEvidenceFile(evidenceFile))
    })

    // Redirect to case overview (for now, go to dashboard)
    router.push('/dashboard')
  }

  return (
    <AppLayout>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Create New Case</h1>
          <p className="mt-2 text-gray-600">
            Enter case details and upload evidence for AI-powered analysis.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left Column - Case Details Form */}
            <Card className="p-6">
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4">Case Details</h3>
                </div>

                <div className="space-y-4">
                  <div>
                    <Label htmlFor="caseTitle">Case Title *</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="caseTitle"
                        value={caseTitle}
                        onChange={(e) => setCaseTitle(e.target.value)}
                        placeholder="Enter case title..."
                        required
                      />
                      {aiSuggestions?.caseTitle && caseTitle !== aiSuggestions.caseTitle && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applySuggestion('caseTitle', aiSuggestions.caseTitle!)}
                        >
                          <Sparkles className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                    {aiSuggestions?.caseTitle && (
                      <p className="text-xs text-blue-600 mt-1">
                        AI suggests: "{aiSuggestions.caseTitle}"
                      </p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="clientName">Client Name *</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="clientName"
                        value={clientName}
                        onChange={(e) => setClientName(e.target.value)}
                        placeholder="Enter client name..."
                        required
                      />
                      {aiSuggestions?.clientName && clientName !== aiSuggestions.clientName && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applySuggestion('clientName', aiSuggestions.clientName!)}
                        >
                          <Sparkles className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                    {aiSuggestions?.clientName && (
                      <p className="text-xs text-blue-600 mt-1">
                        AI suggests: "{aiSuggestions.clientName}"
                      </p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="caseType">Case Type *</Label>
                    <div className="flex items-center gap-2">
                      <Select value={caseType} onValueChange={setCaseType} required>
                        <SelectTrigger>
                          <SelectValue placeholder="Select case type..." />
                        </SelectTrigger>
                        <SelectContent>
                          {caseTypes.map(type => (
                            <SelectItem key={type} value={type}>{type}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {aiSuggestions?.caseType && caseType !== aiSuggestions.caseType && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applySuggestion('caseType', aiSuggestions.caseType!)}
                        >
                          <Sparkles className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                    {aiSuggestions?.caseType && (
                      <p className="text-xs text-blue-600 mt-1">
                        AI suggests: "{aiSuggestions.caseType}"
                      </p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="description">Description</Label>
                    <div className="flex flex-col gap-2">
                      <Textarea
                        id="description"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Enter case description..."
                        rows={4}
                      />
                      {aiSuggestions?.description && description !== aiSuggestions.description && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="self-start"
                          onClick={() => applySuggestion('description', aiSuggestions.description!)}
                        >
                          <Sparkles className="h-3 w-3 mr-1" />
                          Use AI Description
                        </Button>
                      )}
                    </div>
                    {aiSuggestions?.description && (
                      <p className="text-xs text-blue-600 mt-1">
                        AI suggests: "{aiSuggestions.description.substring(0, 100)}..."
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </Card>

            {/* Right Column - Evidence Upload */}
            <Card className="p-6">
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Evidence Upload</h3>
                  {isAnalyzing && (
                    <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                      <Sparkles className="h-3 w-3 mr-1 animate-spin" />
                      Analyzing...
                    </Badge>
                  )}
                  {aiSuggestions && (
                    <Badge variant="secondary" className="bg-green-100 text-green-800">
                      {aiSuggestions.confidence}% confidence
                    </Badge>
                  )}
                </div>

                <FileDropzone onFilesSelected={handleFilesSelected} />

                {/* Uploaded Files List */}
                {uploadedFiles.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium">Uploaded Files</h4>
                    {uploadedFiles.map(({ file, id }) => (
                      <div key={id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                        <span className="text-sm truncate">{file.name}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(id)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Submit Button */}
          <div className="mt-8 flex justify-end">
            <Button
              type="submit"
              className="bg-orange-500 hover:bg-orange-600 px-8"
              disabled={!caseTitle || !clientName || !caseType}
            >
              Create Case
            </Button>
          </div>
        </form>
      </div>
    </AppLayout>
  )
}