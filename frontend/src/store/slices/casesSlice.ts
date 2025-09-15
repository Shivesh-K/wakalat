import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface Case {
  caseId: string
  title: string
  client: string
  caseType: string
  status: 'active' | 'completed' | 'archived'
  createdAt: string
  updatedAt: string
  deletedAt?: string
}

interface CasesState {
  cases: Case[]
  loading: boolean
  error: string | null
}

const initialState: CasesState = {
  cases: [
    {
      caseId: '1',
      title: 'People v. Johnson',
      client: 'Marcus Johnson',
      caseType: 'Criminal Defense',
      status: 'active',
      createdAt: '2024-01-20',
      updatedAt: '2024-01-20'
    },
    {
      caseId: '2',
      title: 'Smith v. Construction Corp',
      client: 'Jennifer Smith',
      caseType: 'Personal Injury',
      status: 'active',
      createdAt: '2024-01-18',
      updatedAt: '2024-01-18'
    },
    {
      caseId: '3',
      title: 'Davis v. Insurance Co',
      client: 'Robert Davis',
      caseType: 'Contract Dispute',
      status: 'active',
      createdAt: '2024-01-15',
      updatedAt: '2024-01-16'
    },
    {
      caseId: '4',
      title: 'Wilson Family Trust',
      client: 'Margaret Wilson',
      caseType: 'Estate Planning',
      status: 'completed',
      createdAt: '2024-01-10',
      updatedAt: '2024-01-14'
    },
    {
      caseId: '5',
      title: 'Brown v. City Council',
      client: 'David Brown',
      caseType: 'Administrative Law',
      status: 'active',
      createdAt: '2024-01-08',
      updatedAt: '2024-01-12'
    },
    {
      caseId: '6',
      title: 'Miller Estate Dispute',
      client: 'Sarah Miller',
      caseType: 'Probate',
      status: 'archived',
      createdAt: '2023-12-15',
      updatedAt: '2024-01-05'
    }
  ],
  loading: false,
  error: null
}

const casesSlice = createSlice({
  name: 'cases',
  initialState,
  reducers: {
    addCase: (state, action: PayloadAction<Case>) => {
      state.cases.unshift(action.payload)
    },
    updateCase: (state, action: PayloadAction<Case>) => {
      const index = state.cases.findIndex(c => c.caseId === action.payload.caseId)
      if (index !== -1) {
        state.cases[index] = action.payload
      }
    },
    softDeleteCase: (state, action: PayloadAction<string>) => {
      const index = state.cases.findIndex(c => c.caseId === action.payload)
      if (index !== -1) {
        state.cases[index].deletedAt = new Date().toISOString()
        state.cases[index].updatedAt = new Date().toISOString()
      }
    },
    restoreCase: (state, action: PayloadAction<string>) => {
      const index = state.cases.findIndex(c => c.caseId === action.payload)
      if (index !== -1) {
        delete state.cases[index].deletedAt
        state.cases[index].updatedAt = new Date().toISOString()
      }
    },
    setCases: (state, action: PayloadAction<Case[]>) => {
      state.cases = action.payload
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
  addCase,
  updateCase,
  softDeleteCase,
  restoreCase,
  setCases,
  setLoading,
  setError
} = casesSlice.actions

export default casesSlice.reducer