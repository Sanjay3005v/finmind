"use client";

import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function ToggleSwitch({
  checked,
  onCheckedChange,
  label,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        checked ? "bg-primary" : "bg-[var(--neutral-800)]"
      )}
    >
      <span
        className={cn(
          "inline-block size-4 rounded-full bg-background transition-transform",
          checked ? "translate-x-[18px]" : "translate-x-[2px]"
        )}
      />
    </button>
  );
}

type AgentToggle = {
  key: string;
  label: string;
  helper: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
};

export function AgentBehaviourCard() {
  const [requireCitations, setRequireCitations] = useState(true);
  const [humanApproval, setHumanApproval] = useState(true);
  const [proactiveAlerts, setProactiveAlerts] = useState(false);

  const toggles: AgentToggle[] = [
    {
      key: "require-citations",
      label: "Require citations",
      helper: "Agents must cite a source for every factual claim",
      checked: requireCitations,
      onChange: setRequireCitations,
    },
    {
      key: "human-approval",
      label: "Human approval for trades",
      helper: "No order reaches a broker without your explicit approval",
      checked: humanApproval,
      onChange: setHumanApproval,
    },
    {
      key: "proactive-alerts",
      label: "Proactive alerts",
      helper: "Let agents surface risk or allocation alerts without being asked",
      checked: proactiveAlerts,
      onChange: setProactiveAlerts,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent behaviour</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {toggles.map((toggle) => (
          <div key={toggle.key} className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-0.5">
              <span className="text-[13px] font-medium text-foreground">{toggle.label}</span>
              <span className="text-[11px] text-muted-foreground">{toggle.helper}</span>
            </div>
            <ToggleSwitch checked={toggle.checked} onCheckedChange={toggle.onChange} label={toggle.label} />
          </div>
        ))}
        <p className="border-t border-border pt-3 text-[11px] text-muted-foreground">
          Preferences apply to this session only — persistence is on the roadmap.
        </p>
      </CardContent>
    </Card>
  );
}

const LLM_PROVIDERS = [
  { name: "OpenAI", model: "gpt-4.1-mini / gpt-4.1", status: "Primary" },
  { name: "Groq", model: "llama-3.3-70b-versatile", status: "Fallback" },
  { name: "Gemini", model: "gemini-2.0-flash", status: "Fallback" },
] as const;

export function LlmRoutingCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM routing</CardTitle>
        <CardDescription>Automatic provider fallback chain</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-3">
          {LLM_PROVIDERS.map((provider, index) => (
            <li key={provider.name} className="flex items-center gap-3">
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent-900)] text-[11px] font-medium text-primary">
                {index + 1}
              </span>
              <div className="flex flex-1 flex-col">
                <span className="text-[13px] text-foreground">{provider.name}</span>
                <span className="text-[11px] text-muted-foreground">{provider.model}</span>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase",
                  provider.status === "Primary"
                    ? "bg-primary/10 text-primary"
                    : "bg-[var(--neutral-900)] text-[var(--neutral-500)]"
                )}
              >
                {provider.status}
              </span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
