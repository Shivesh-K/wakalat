import { configureStore } from '@reduxjs/toolkit'
import { counterSlice } from './slices/counterSlice'
import casesReducer from './slices/casesSlice'
import evidenceReducer from './slices/evidenceSlice'
import argumentsReducer from './slices/argumentsSlice'
import researchReducer from './slices/researchSlice'

export const makeStore = () => {
  return configureStore({
    reducer: {
      counter: counterSlice.reducer,
      cases: casesReducer,
      evidence: evidenceReducer,
      arguments: argumentsReducer,
      research: researchReducer,
    },
  })
}

export type AppStore = ReturnType<typeof makeStore>
export type RootState = ReturnType<AppStore['getState']>
export type AppDispatch = AppStore['dispatch']