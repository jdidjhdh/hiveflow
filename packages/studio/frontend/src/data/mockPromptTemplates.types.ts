export interface TemplateItem {
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
  variables: string[];
  model_hints: string[];
  current_version: number;
  total_versions: number;
  created_at: number;
  updated_at: number;
}

export interface TemplateDetail extends TemplateItem {
  content: string;
  requested_version: number;
}

export interface VersionInfo {
  version: number;
  created_at: number;
  created_by: string;
  change_summary: string;
  content_length: number;
}
