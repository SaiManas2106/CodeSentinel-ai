"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { connectRepository, getRepositories, syncRepository } from "@/lib/api";

export default function RepositoriesPage(): JSX.Element {
  const queryClient = useQueryClient();
  const repos = useQuery({ queryKey: ["repositories"], queryFn: getRepositories });

  const connect = useMutation({
    mutationFn: () => connectRepository({ github_repo_id: Date.now(), full_name: "org/new-repo", owner: "org" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["repositories"] });
    }
  });

  const sync = useMutation({
    mutationFn: (repoId: string) => syncRepository(repoId)
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Repositories</h1>
        <button onClick={() => connect.mutate()} className="rounded-md bg-primary px-4 py-2 text-primary-foreground">Connect New Repository</button>
      </div>

      {repos.isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-28 animate-pulse rounded-lg border border-border bg-card" />)}
        </div>
      ) : (repos.data ?? []).length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">No repositories connected yet.</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(repos.data ?? []).map((repo) => (
            <div key={repo.id} className="rounded-lg border border-border bg-card p-4">
              <h2 className="font-semibold">{repo.full_name}</h2>
              <p className="text-xs text-muted-foreground">{repo.language ?? "Unknown language"}</p>
              <p className="mt-2 text-sm">PRs: {repo.pr_count ?? 0}</p>
              <p className="text-sm">Avg score: {(repo.avg_score ?? 0).toFixed(1)}</p>
              <p className={`mt-1 text-xs ${repo.is_active ? "text-green-400" : "text-red-400"}`}>{repo.is_active ? "Active" : "Inactive"}</p>
              <button onClick={() => sync.mutate(repo.id)} className="mt-3 rounded-md border border-border px-3 py-1 text-sm">Sync</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
