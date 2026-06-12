import { useMemo } from 'react';
import { useLocaleStore, type StudioLocale } from '@/store/useLocaleStore';
import zh, { type LocaleCatalog } from './locales/zh';
import en from './locales/en';

const catalogs = { zh, en } as const;

type NestedKeyOf<T, Prefix extends string = ''> = T extends object
  ? {
      [K in keyof T & string]: T[K] extends readonly string[]
        ? `${Prefix}${K}`
        : T[K] extends object
          ? NestedKeyOf<T[K], `${Prefix}${K}.`>
          : `${Prefix}${K}`;
    }[keyof T & string]
  : never;

export type MessageKey = NestedKeyOf<LocaleCatalog>;

export type TranslateParams = Record<string, string | number>;

function resolve(obj: unknown, path: string): string | undefined {
  const parts = path.split('.');
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return typeof cur === 'string' ? cur : undefined;
}

function applyParams(text: string, params?: TranslateParams): string {
  if (!params) return text;
  return Object.entries(params).reduce(
    (acc, [key, val]) => acc.replace(new RegExp(`\\{${key}\\}`, 'g'), String(val)),
    text,
  );
}

export function translate(
  locale: StudioLocale,
  key: MessageKey,
  params?: TranslateParams,
): string {
  const raw = resolve(catalogs[locale], key) ?? key;
  return applyParams(raw, params);
}

export function useI18n() {
  const locale = useLocaleStore((s) => s.locale);
  const setLocale = useLocaleStore((s) => s.setLocale);
  const t = useMemo(
    () => (key: MessageKey, params?: TranslateParams) => translate(locale, key, params),
    [locale],
  );
  return { locale, setLocale, t };
}

export type { LocaleCatalog } from './locales/catalog';
