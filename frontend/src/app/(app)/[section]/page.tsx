// Placeholder for page-map sections that land in later phases
// (docs/team/implementation-roadmap.md). Each gets its real feature folder
// under src/features/<area> when its phase starts.
const SECTIONS: Record<string, { title: string; phase: string; blurb: string }> = {
};

export function generateStaticParams() {
  return Object.keys(SECTIONS).map((section) => ({ section }));
}

export default function SectionPlaceholder({ params }: { params: { section: string } }) {
  const meta = SECTIONS[params.section] ?? {
    title: params.section,
    phase: "later",
    blurb: "Not yet scheduled.",
  };
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">{meta.title}</h1>
      <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center">
        <p className="text-sm text-slate-500">{meta.blurb}</p>
        <p className="mt-3 inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          arrives in {meta.phase}
        </p>
      </div>
    </div>
  );
}
