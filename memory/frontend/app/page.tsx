"use client";

import { useState } from "react";
import ConflictLog from "@/components/ConflictLog";
import DecayCurve from "@/components/DecayCurve";
import Playground from "@/components/Playground";
import ProvenanceExplorer from "@/components/ProvenanceExplorer";
import StatsPanel from "@/components/StatsPanel";

export default function Dashboard() {
  const [userId, setUserId] = useState("demo-user");
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedMemory, setSelectedMemory] = useState<string | null>(null);

  const refresh = () => setRefreshKey((k) => k + 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-400">User</label>
        <input
          className="input w-48"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        />
        <button className="btn" onClick={refresh}>
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <StatsPanel refreshKey={refreshKey} />
          <Playground
            userId={userId}
            onChange={refresh}
            onSelectMemory={setSelectedMemory}
          />
          <ConflictLog userId={userId} refreshKey={refreshKey} />
        </div>
        <div className="space-y-6">
          <DecayCurve />
          <ProvenanceExplorer memoryId={selectedMemory} />
        </div>
      </div>
    </div>
  );
}
