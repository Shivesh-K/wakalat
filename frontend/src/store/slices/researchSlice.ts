import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface CasePrecedent {
  precedentId: string
  title: string
  citation: string
  year: string
  court: string
  practiceArea: string[]
  jurisdiction: string
  relevanceScore: number
  summary: string
  keyHolding: string
  tags: string[]
  isFavorited: boolean
}

export interface ResearchQuery {
  queryId: string
  caseId?: string
  searchTerms: string
  filters: {
    practiceAreas: string[]
    jurisdictions: string[]
    courts: string[]
  }
  results: CasePrecedent[]
  totalResults: number
  createdAt: string
  updatedAt: string
  deletedAt?: string
}

export interface ResearchHistory {
  historyId: string
  searchTerm: string
  timestamp: string
}

interface ResearchState {
  queries: ResearchQuery[]
  searchHistory: ResearchHistory[]
  quickCitations: {
    mostCited: CasePrecedent[]
    mostRelevant: CasePrecedent[]
    recent: CasePrecedent[]
  }
  loading: boolean
  error: string | null
}

const initialState: ResearchState = {
  queries: [
    {
      queryId: '1',
      caseId: '1',
      searchTerms: 'fourth amendment reasonable suspicion traffic stops',
      filters: {
        practiceAreas: ['Criminal Defense'],
        jurisdictions: ['Federal'],
        courts: ['U.S. Supreme Court']
      },
      results: [
        {
          precedentId: '1',
          title: 'Terry v. Ohio',
          citation: '392 U.S. 1 (1968)',
          year: '1968',
          court: 'U.S. Supreme Court',
          practiceArea: ['Criminal Defense'],
          jurisdiction: 'Federal',
          relevanceScore: 95,
          summary: 'Established the standard for reasonable suspicion in stop-and-frisk encounters.',
          keyHolding: 'Police may conduct limited searches when they have reasonable suspicion of criminal activity.',
          tags: ['fourth amendment', 'reasonable suspicion', 'traffic stops'],
          isFavorited: false
        },
        {
          precedentId: '2',
          title: 'Delaware v. Prouse',
          citation: '440 U.S. 648 (1979)',
          year: '1979',
          court: 'U.S. Supreme Court',
          practiceArea: ['Criminal Defense'],
          jurisdiction: 'Federal',
          relevanceScore: 92,
          summary: 'Random traffic stops without reasonable suspicion violate the Fourth Amendment.',
          keyHolding: 'Random vehicle stops for license checks without reasonable suspicion are unconstitutional.',
          tags: ['fourth amendment', 'traffic stops', 'random stops'],
          isFavorited: true
        }
      ],
      totalResults: 5,
      createdAt: '2024-01-20',
      updatedAt: '2024-01-20'
    }
  ],
  searchHistory: [
    {
      historyId: '1',
      searchTerm: 'Fourth Amendment',
      timestamp: 'Today'
    },
    {
      historyId: '2',
      searchTerm: 'Traffic Stops',
      timestamp: 'Yesterday'
    },
    {
      historyId: '3',
      searchTerm: 'DUI Evidence',
      timestamp: '2 days ago'
    }
  ],
  quickCitations: {
    mostCited: [
      {
        precedentId: '1',
        title: 'Terry v. Ohio (1968)',
        citation: '392 U.S. 1',
        year: '1968',
        court: 'U.S. Supreme Court',
        practiceArea: ['Criminal Defense'],
        jurisdiction: 'Federal',
        relevanceScore: 95,
        summary: 'Established reasonable suspicion standard',
        keyHolding: '',
        tags: [],
        isFavorited: false
      }
    ],
    mostRelevant: [
      {
        precedentId: '2',
        title: 'Delaware v. Prouse (1979)',
        citation: '440 U.S. 648',
        year: '1979',
        court: 'U.S. Supreme Court',
        practiceArea: ['Criminal Defense'],
        jurisdiction: 'Federal',
        relevanceScore: 92,
        summary: 'Random stops unconstitutional',
        keyHolding: '',
        tags: [],
        isFavorited: false
      }
    ],
    recent: [
      {
        precedentId: '5',
        title: 'Rodriguez v. United States (2015)',
        citation: '575 U.S. 348',
        year: '2015',
        court: 'U.S. Supreme Court',
        practiceArea: ['Criminal Defense'],
        jurisdiction: 'Federal',
        relevanceScore: 87,
        summary: 'Traffic stop duration limits',
        keyHolding: '',
        tags: [],
        isFavorited: false
      }
    ]
  },
  loading: false,
  error: null
}

const researchSlice = createSlice({
  name: 'research',
  initialState,
  reducers: {
    addQuery: (state, action: PayloadAction<ResearchQuery>) => {
      state.queries.unshift(action.payload)
    },
    updateQuery: (state, action: PayloadAction<ResearchQuery>) => {
      const index = state.queries.findIndex(q => q.queryId === action.payload.queryId)
      if (index !== -1) {
        state.queries[index] = action.payload
      }
    },
    toggleFavorite: (state, action: PayloadAction<string>) => {
      state.queries.forEach(query => {
        const precedent = query.results.find(p => p.precedentId === action.payload)
        if (precedent) {
          precedent.isFavorited = !precedent.isFavorited
        }
      })
    },
    addToSearchHistory: (state, action: PayloadAction<{ searchTerm: string; timestamp: string }>) => {
      const newHistory: ResearchHistory = {
        historyId: Date.now().toString(),
        searchTerm: action.payload.searchTerm,
        timestamp: action.payload.timestamp
      }
      state.searchHistory.unshift(newHistory)
      if (state.searchHistory.length > 10) {
        state.searchHistory.pop()
      }
    },
    softDeleteQuery: (state, action: PayloadAction<string>) => {
      const index = state.queries.findIndex(q => q.queryId === action.payload)
      if (index !== -1) {
        state.queries[index].deletedAt = new Date().toISOString()
      }
    },
    setQueries: (state, action: PayloadAction<ResearchQuery[]>) => {
      state.queries = action.payload
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
  addQuery,
  updateQuery,
  toggleFavorite,
  addToSearchHistory,
  softDeleteQuery,
  setQueries,
  setLoading,
  setError
} = researchSlice.actions

export default researchSlice.reducer