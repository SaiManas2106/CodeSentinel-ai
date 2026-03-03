import TrendChart from "@/components/charts/TrendChart";
import DonutChart from "@/components/charts/DonutChart";
import ScoreBadge from "@/components/ui/ScoreBadge";
import { getDashboardStats, getReviews, getScoreTrends } from "@/lib/api";

export default async function DashboardPage(): Promise<JSX.Element> {
  const [stats, reviews, trends] = await Promise.all([getDashboardStats(), getReviews(1, 10), getScoreTrends()]);

  const issueBreakdown = [
    { name: "Security", value: 18 },
    { name: "Bugs", value: 24 },
    { name: "Standards", value: 14 },
    { name: "Performance", value: 8 },
    { name: "Docs", value: 6 }
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-sm text-muted-foreground">Total PRs Reviewed</p><p className="text-2xl font-bold">{stats.total_prs_reviewed}</p><p className="text-xs text-green-400">+12% vs last month</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-sm text-muted-foreground">Average Score</p><p className="text-2xl font-bold">{stats.average_score.toFixed(1)}</p><p className="text-xs text-green-400">+3.4 points</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-sm text-muted-foreground">Issues Found</p><p className="text-2xl font-bold">{stats.issues_found}</p><p className="text-xs text-yellow-400">Stable trend</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-sm text-muted-foreground">Time Saved</p><p className="text-2xl font-bold">{stats.time_saved_hours}h</p><p className="text-xs text-green-400">+22% efficiency</p></div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          {trends.length > 0 ? <TrendChart data={trends} /> : <div className="rounded-lg border border-border bg-card p-8 text-sm text-muted-foreground">No trend data available yet.</div>}
        </div>
        <div>
          <DonutChart data={issueBreakdown} />
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-4 text-lg font-semibold">Recent Reviews</h2>
        {reviews.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reviews yet. Connect a repository to begin automatic PR analysis.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2">PR</th><th>Score</th><th>Status</th><th>Time</th></tr></thead>
            <tbody>
              {reviews.items.map((review) => (
                <tr key={review.id} className="border-b border-border/50">
                  <td className="py-2">{review.id.slice(0, 8)}...</td>
                  <td><ScoreBadge score={review.overall_score} /></td>
                  <td>{review.status}</td>
                  <td>{new Date(review.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-lg font-semibold">Top Repositories</h2>
        <ul className="space-y-2 text-sm">
          <li className="flex justify-between"><span>org/backend-core</span><span className="text-muted-foreground">64 reviews</span></li>
          <li className="flex justify-between"><span>org/frontend-app</span><span className="text-muted-foreground">48 reviews</span></li>
          <li className="flex justify-between"><span>org/platform-sdk</span><span className="text-muted-foreground">31 reviews</span></li>
        </ul>
      </div>
    </div>
  );
}
