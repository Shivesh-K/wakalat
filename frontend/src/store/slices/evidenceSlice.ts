import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface EvidenceFile {
  evidenceId: string
  caseId: string
  filename: string
  uploadedAt: string
  relevanceScore: 'high' | 'medium' | 'low'
  description?: string
  extractedText?: string
  deletedAt?: string
}

interface EvidenceState {
  evidenceFiles: EvidenceFile[]
  loading: boolean
  error: string | null
}

const initialState: EvidenceState = {
  evidenceFiles: [
    {
      evidenceId: '1',
      caseId: '1',
      filename: 'police_report.pdf',
      uploadedAt: '2024-01-15',
      relevanceScore: 'high',
      description: 'Initial police report detailing the traffic stop and arrest procedures.'
    },
    {
      evidenceId: '2',
      caseId: '2',
      filename: 'breathalyzer_calibration.pdf',
      uploadedAt: '2024-01-16',
      relevanceScore: 'high',
      description: 'Breathalyzer calibration records showing potential maintenance issues.'
    },
    {
      evidenceId: '3',
      caseId: '1',
      filename: 'witness_statement.docx',
      uploadedAt: '2024-01-14',
      relevanceScore: 'medium',
      description: 'Witness testimony from traffic incident.'
    }
  ],
  loading: false,
  error: null
}

const evidenceSlice = createSlice({
  name: 'evidence',
  initialState,
  reducers: {
    addEvidenceFile: (state, action: PayloadAction<EvidenceFile>) => {
      state.evidenceFiles.unshift(action.payload)
    },
    updateEvidenceFile: (state, action: PayloadAction<EvidenceFile>) => {
      const index = state.evidenceFiles.findIndex(e => e.evidenceId === action.payload.evidenceId)
      if (index !== -1) {
        state.evidenceFiles[index] = action.payload
      }
    },
    softDeleteEvidenceFile: (state, action: PayloadAction<string>) => {
      const index = state.evidenceFiles.findIndex(e => e.evidenceId === action.payload)
      if (index !== -1) {
        state.evidenceFiles[index].deletedAt = new Date().toISOString()
      }
    },
    restoreEvidenceFile: (state, action: PayloadAction<string>) => {
      const index = state.evidenceFiles.findIndex(e => e.evidenceId === action.payload)
      if (index !== -1) {
        delete state.evidenceFiles[index].deletedAt
      }
    },
    setEvidenceFiles: (state, action: PayloadAction<EvidenceFile[]>) => {
      state.evidenceFiles = action.payload
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload
    }
  }
})

export const {
  addEvidenceFile,
  updateEvidenceFile,
  softDeleteEvidenceFile,
  restoreEvidenceFile,
  setEvidenceFiles,
  setLoading,
  setError
} = evidenceSlice.actions

export default evidenceSlice.reducer