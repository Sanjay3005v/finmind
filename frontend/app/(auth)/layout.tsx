import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[1.05fr_0.95fr]">
      <BrandPanel />
      <div className="flex items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-[360px]">{children}</div>
      </div>
    </div>
  );
}

function BrandPanel() {
  return (
    <div
      className="relative hidden flex-col justify-between overflow-hidden p-14 lg:flex"
      style={{
        background: "linear-gradient(160deg, #1b1e33, #161826 55%, #141525)",
      }}
    >
      <div
        className="pointer-events-none absolute -left-45 -top-50 size-[620px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(145,132,217,0.20), transparent 65%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(#ffffff08 1px, transparent 1px), linear-gradient(90deg, #ffffff08 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(circle at 30% 40%, #000, transparent 75%)",
          WebkitMaskImage: "radial-gradient(circle at 30% 40%, #000, transparent 75%)",
        }}
      />

      <div className="relative flex items-center gap-2.5">
        <span className="flex size-[30px] items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-[inset_0_0_0_1px_var(--accent-700)]">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 19h16M7 15l4-5 3 3 5-7" />
          </svg>
        </span>
        <span className="text-[13px] font-medium tracking-[0.18em] text-foreground uppercase">
          FINMIND
        </span>
      </div>

      <div className="relative max-w-[460px]">
        <p className="mb-3 text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
          AI Investment Research
        </p>
        <h1 className="mb-4 text-[46px] leading-[1.08] font-medium tracking-[-0.03em] text-foreground">
          An analyst that shows its working.
        </h1>
        <p className="text-[15px] leading-[1.7] text-muted-foreground">
          FINMIND connects to your brokerage accounts and research library to give you a
          deterministic, cited, human-approved AI analyst — every number sourced, every trade
          reviewed by you.
        </p>

        <div className="mt-10 grid grid-cols-3 gap-6">
          <StatColumn value="4" label="Brokers" />
          <StatColumn value="100%" label="Cited answers" />
          <StatColumn value="0" label="Unapproved trades" />
        </div>
      </div>

      <p className="relative text-[11px] text-[var(--neutral-700)]">
        Paper mode by default · LangGraph agents · pgvector RAG
      </p>
    </div>
  );
}

function StatColumn({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-2xl font-medium tracking-[-0.02em] text-foreground">{value}</div>
      <div className="mt-1 text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}
