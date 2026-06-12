export interface PluginMarketplaceItem {
  plugin_id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author: string;
  status: 'available' | 'installed';
  tags: string[];
  created_at: number;
}

export const MOCK_MARKETPLACE_CATEGORIES: Record<string, string> = {
  integration: '集成',
  nlp: 'NLP',
  tools: '工具',
};

export const MOCK_MARKETPLACE_PLUGINS: PluginMarketplaceItem[] = [
  {
    plugin_id: 'demo-web-search',
    name: 'Web Search (Demo)',
    description: '演示用搜索 Skill 插件，Mock 模式下不可安装。',
    category: 'integration',
    version: '0.1.0',
    author: 'HiveFlow',
    status: 'available',
    tags: ['search', 'web'],
    created_at: Date.now() - 86400000,
  },
  {
    plugin_id: 'demo-summarizer',
    name: 'Text Summarizer (Demo)',
    description: '演示用摘要 Skill，切换真实模式后可尝试安装。',
    category: 'nlp',
    version: '0.2.0',
    author: 'HiveFlow',
    status: 'available',
    tags: ['nlp', 'summarization'],
    created_at: Date.now() - 172800000,
  },
];

export function mockMarketplaceStats(plugins: PluginMarketplaceItem[]) {
  const by_category: Record<string, number> = {};
  for (const p of plugins) {
    by_category[p.category] = (by_category[p.category] || 0) + 1;
  }
  return { total: plugins.length, by_category };
}
