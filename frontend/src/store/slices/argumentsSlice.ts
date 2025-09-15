import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface Argument {
  argumentId: string
  caseId: string
  title: string
  strategy: string
  description: string
  strengths: string[]
  challenges: string[]
  supportingEvidence: string[]
  generatedAt: string
  updatedAt: string
  deletedAt?: string
}

interface ArgumentsState {
  arguments: Argument[]
  loading: boolean
  error: string | null
}

const initialState: ArgumentsState = {
  arguments: [
    {
      argumentId: '1',
      caseId: '1',
      title: 'Motion to Suppress Evidence - Improper Traffic Stop',
      strategy: 'Challenge the initial stop under Fourth Amendment grounds',
      description: 'The traffic stop was conducted without reasonable suspicion. Officer testimony regarding "weaving" is uncorroborated by video evidence, and the stop appears pretextual in nature.',
      strengths: [
        'No objective evidence of traffic violation',
        'Officer\'s training record shows limited DUI enforcement experience',
        'Stop occurred in area known for frequent pretextual stops'
      ],
      challenges: [
        'Client admitted to consuming alcohol',
        'Strong odor of alcohol noted by officer'
      ],
      supportingEvidence: ['1', '3'],
      generatedAt: '2024-01-20',
      updatedAt: '2024-01-20'
    },
    {
      argumentId: '2',
      caseId: '2',
      title: 'Motion to Exclude Breathalyzer Results',
      strategy: 'Challenge accuracy due to improper maintenance',
      description: 'The breathalyzer device used showed maintenance irregularities that could significantly affect the accuracy of the test results.',
      strengths: [
        'Calibration records show missed maintenance windows',
        'Device manufacturer recalls during relevant period',
        'No certified technician present during test'
      ],
      challenges: [
        'Multiple failed field sobriety tests',
        'Officer observed clear signs of impairment'
      ],
      supportingEvidence: ['2'],
      generatedAt: '2024-01-18',
      updatedAt: '2024-01-18'
    }
  ],
  loading: false,
  error: null
}

const argumentsSlice = createSlice({
  name: 'arguments',
  initialState,
  reducers: {
    addArgument: (state, action: PayloadAction<Argument>) => {
      state.arguments.unshift(action.payload)
    },
    updateArgument: (state, action: PayloadAction<Argument>) => {
      const index = state.arguments.findIndex(a => a.argumentId === action.payload.argumentId)
      if (index !== -1) {
        state.arguments[index] = action.payload
      }
    },
    softDeleteArgument: (state, action: PayloadAction<string>) => {
      const index = state.arguments.findIndex(a => a.argumentId === action.payload)
      if (index !== -1) {
        state.arguments[index].deletedAt = new Date().toISOString()
        state.arguments[index].updatedAt = new Date().toISOString()
      }
    },
    restoreArgument: (state, action: PayloadAction<string>) => {
      const index = state.arguments.findIndex(a => a.argumentId === action.payload)
      if (index !== -1) {
        delete state.arguments[index].deletedAt
        state.arguments[index].updatedAt = new Date().toISOString()
      }
    },
    setArguments: (state, action: PayloadAction<Argument[]>) => {
      state.arguments = action.payload
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
  addArgument,
  updateArgument,
  softDeleteArgument,
  restoreArgument,
  setArguments,
  setLoading,
  setError
} = argumentsSlice.actions

export default argumentsSlice.reducer