import axios, { AxiosError, AxiosInstance } from "axios";
import type { DashboardStats, PaginatedResponse, Repository, Review, TrendData } from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const client: AxiosInstance = axios.create({
  baseURL: apiBase,
  timeout: 15000
});

let isRefreshing = false;
let refreshPromise: Promise<string> | null = null;

client.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

async function refreshToken(): Promise<string> {
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) throw new Error("Missing refresh token");
  const resp = await axios.post(`${apiBase}/auth/refresh`, { refresh_token: refresh });
  localStorage.setItem("access_token", resp.data.access_token);
  localStorage.setItem("refresh_token", resp.data.refresh_token);
  return resp.data.access_token as string;
}

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original.headers["x-retried"]) {
      if (!isRefreshing) {
        isRefreshing = true;
        refreshPromise = refreshToken().finally(() => {
          isRefreshing = false;
        });
      }
      const token = await refreshPromise;
      original.headers.Authorization = `Bearer ${token}`;
      original.headers["x-retried"] = "1";
      return client(original);
    }
    return Promise.reject(error);
  }
);

export async function getReviews(page = 1, pageSize = 20): Promise<PaginatedResponse<Review>> {
  const { data } = await client.get<PaginatedResponse<Review>>("/reviews", { params: { page, page_size: pageSize } });
  return data;
}

export async function getReview(reviewId: string): Promise<Review> {
  const { data } = await client.get<Review>(`/reviews/${reviewId}`);
  return data;
}

export async function getRepositories(): Promise<Repository[]> {
  const { data } = await client.get<Repository[]>("/repositories");
  return data;
}

export async function connectRepository(payload: Partial<Repository>): Promise<{ id: string; status: string }> {
  const { data } = await client.post<{ id: string; status: string }>("/repositories", payload);
  return data;
}

export async function syncRepository(repoId: string): Promise<{ status: string }> {
  const { data } = await client.post<{ status: string }>(`/repositories/${repoId}/sync`);
  return data;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await client.get<{ total_reviews: number; avg_overall_score: number }>("/reviews/stats/summary");
  return {
    total_prs_reviewed: data.total_reviews,
    average_score: data.avg_overall_score,
    issues_found: 0,
    time_saved_hours: 0
  };
}

export async function getScoreTrends(): Promise<TrendData[]> {
  const reviews = await getReviews(1, 100);
  const grouped = new Map<string, { overall: number[]; security: number[]; standards: number[] }>();

  for (const review of reviews.items) {
    const key = review.created_at.slice(0, 10);
    const row = grouped.get(key) ?? { overall: [], security: [], standards: [] };
    row.overall.push(review.overall_score);
    row.security.push(review.security_score);
    row.standards.push(review.standards_score);
    grouped.set(key, row);
  }

  return [...grouped.entries()].map(([date, scores]) => ({
    date,
    overall: scores.overall.reduce((a, b) => a + b, 0) / Math.max(scores.overall.length, 1),
    security: scores.security.reduce((a, b) => a + b, 0) / Math.max(scores.security.length, 1),
    standards: scores.standards.reduce((a, b) => a + b, 0) / Math.max(scores.standards.length, 1)
  }));
}
