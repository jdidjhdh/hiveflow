import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type StudioLocale = 'zh' | 'en';

interface LocaleState {
  locale: StudioLocale;
  setLocale: (locale: StudioLocale) => void;
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    (set) => ({
      locale: 'zh',
      setLocale: (locale) => set({ locale }),
    }),
    { name: 'hiveflow-studio-locale' },
  ),
);
