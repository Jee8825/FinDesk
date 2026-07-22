// Placeholder for page-map sections that land in later phases
// (docs/team/implementation-roadmap.md). Each gets its real feature folder
// under src/features/<area> when its phase starts.
const SECTIONS: Record<string, { title: string; phase: string; blurb: string }> = {};

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
    <div className="px-8 py-10">
      <h1 className="text-2xl font-bold text-ink">{meta.title}</h1>
      <div className="mt-6 max-w-xl rounded-2xl border-2 border-dashed border-line p-12 text-center">
        <p className="text-sm text-faint">{meta.blurb}</p>
        <p className="mono-label mt-3 inline-block rounded-full border border-line bg-white/[0.05] px-3 py-1.5 text-mute">
          arrives in {meta.phase}
        </p>
      </div>
    </div>
  );
}
