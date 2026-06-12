import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { downloadJson, downloadText } from '@/utils/downloadFile';

describe('downloadFile helpers', () => {
  let clickSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clickSpy = vi.fn();
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    vi.spyOn(document, 'createElement').mockReturnValue({
      click: clickSpy,
      href: '',
      download: '',
    } as unknown as HTMLAnchorElement);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('downloadJson triggers anchor click with filename', () => {
    downloadJson({ ok: true }, 'test.json');
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
  });

  it('downloadText triggers anchor click', () => {
    downloadText('hello', 'out.txt', 'text/plain');
    expect(clickSpy).toHaveBeenCalledOnce();
  });
});
