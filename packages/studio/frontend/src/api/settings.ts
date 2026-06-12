import { apiFetch } from './client';

export interface SchedulerSettings {
  strategy: 'least_loaded' | 'auction';
  auction_timeout: number;
}

export async function getSchedulerSettings(): Promise<SchedulerSettings> {
  const data = await apiFetch('/api/settings/scheduler');
  return {
    strategy: data.strategy === 'auction' ? 'auction' : 'least_loaded',
    auction_timeout: Number(data.auction_timeout ?? 5),
  };
}

export async function updateSchedulerSettings(settings: SchedulerSettings): Promise<SchedulerSettings> {
  const data = await apiFetch('/api/settings/scheduler', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
  return {
    strategy: data.strategy === 'auction' ? 'auction' : 'least_loaded',
    auction_timeout: Number(data.auction_timeout ?? 5),
  };
}
