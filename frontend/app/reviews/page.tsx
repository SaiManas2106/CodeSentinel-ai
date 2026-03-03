"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ScoreBadge from "@/components/ui/ScoreBadge";
import { getReviews } from "@/lib/api";

export default function ReviewsPage(): JSX.Element {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<"date" | "score">("date");

  const query = useQuery({
    queryKey: ["reviews", page],
    queryFn: () => getReviews(page, 20)
  });

  const rows = useMemo(() => {
    const items = query.data?.items ?? [];
    const filtered = items.filter((item) => {
      const matchSearch = item.id.toLowerCase().includes(search.toLowerCase());
      const matchStatus = status === "all" || item.status === status;
      return matchSearch && matchStatus;
    });
    const sorted = [...filtered].sort((a, b) =>
      sortBy === "score" ? b.overall_score - a.overall_score : +new Date(b.created_at) - +new Date(a.created_at)
    );
    return sorted;
  }, [query.data?.items, search, status, sortBy]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Reviews</h1>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search repo or PR title" className="rounded-md border border-border bg-card px-3 py-2 md:col-span-2" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-border bg-card px-3 py-2">
          <option value="all">All Status</option><option value="pending">Pending</option><option value="processing">Processing</option><option value="completed">Completed</option><option value="failed">Failed</option>
        </select>
        <select className="rounded-md border border-border bg-card px-3 py-2"><option>Score: 0-100</option><option>80-100</option><option>60-79</option><option>0-59</option></select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as "date" | "score")} className="rounded-md border border-border bg-card px-3 py-2">
          <option value="date">Sort by date</option><option value="score">Sort by score</option>
        </select>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        {query.isLoading ? (
          <div className="space-y-2"><div className="h-8 animate-pulse rounded bg-secondary" /><div className="h-8 animate-pulse rounded bg-secondary" /></div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reviews found for current filters.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2">Review ID</th><th>Status</th><th>Score</th><th>Date</th></tr></thead>
            <tbody>
              {rows.map((review) => (
                <tr key={review.id} className="cursor-pointer border-b border-border/50 hover:bg-secondary/40">
                  <td className="py-2">{review.id}</td>
                  <td>{review.status}</td>
                  <td><ScoreBadge score={review.overall_score} /></td>
                  <td>{new Date(review.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <button onClick={() => setPage((v) => Math.max(1, v - 1))} className="rounded-md border border-border px-3 py-2">Previous</button>
        <span className="text-sm text-muted-foreground">Page {page}</span>
        <button onClick={() => setPage((v) => v + 1)} className="rounded-md border border-border px-3 py-2">Next</button>
      </div>
    </div>
  );
}
