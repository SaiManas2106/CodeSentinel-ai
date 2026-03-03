export interface User {
  id: string;
  email: string;
  username: string;
  github_username?: string;
  avatar_url?: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface Repository {
  id: string;
  github_repo_id: number;
  full_name: string;
  owner: string;
  language?: string;
  is_active: boolean;
  avg_score?: number;
  pr_count?: number;
}

export interface PullRequest {
  id: string;
  number: number;
  title: string;
  state: "open" | "closed" | "merged";
  additions: number;
  deletions: number;
}

export interface Issue {
  category: string;
  severity: string;
  title: string;
  description: string;
  file_path?: string;
  line?: number;
}

export interface Suggestion {
  title: string;
  rationale: string;
  suggested_patch?: string;
}

export interface Review {
  id: string;
  pull_request_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  overall_score: number;
  security_score: number;
  standards_score: number;
  quality_score: number;
  summary?: string;
  issues: Issue[];
  suggestions: Suggestion[];
  model_used?: string;
  tokens_used: number;
  processing_time_ms: number;
  created_at: string;
  completed_at?: string;
}

export interface DashboardStats {
  total_prs_reviewed: number;
  average_score: number;
  issues_found: number;
  time_saved_hours: number;
}

export interface TrendData {
  date: string;
  overall: number;
  security: number;
  standards: number;
}

export interface ApiResponse<T> {
  data: T;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
