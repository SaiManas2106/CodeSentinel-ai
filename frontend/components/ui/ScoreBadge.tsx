"use client";

import { motion } from "framer-motion";

interface ScoreBadgeProps {
  score: number;
  label?: string;
}

export default function ScoreBadge({ score, label = "Score" }: ScoreBadgeProps): JSX.Element {
  const colorClass = score >= 80 ? "bg-green-600/20 text-green-400" : score >= 60 ? "bg-yellow-500/20 text-yellow-300" : "bg-red-600/20 text-red-400";

  return (
    <motion.span whileHover={{ scale: 1.05 }} className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${colorClass}`}>
      {label}: {Math.round(score)}
    </motion.span>
  );
}
