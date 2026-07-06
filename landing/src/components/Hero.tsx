import { Eye, RefreshCcw, ShieldCheck } from "lucide-react";
import { Badge } from "./Badge";
import { Pill } from "./Pill";
import { PrimaryButton } from "./Button";
import { MetricsCard } from "./MetricsCard";

export function Hero() {
  return (
    <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 pt-32 pb-10 sm:px-10 lg:px-16">
      <div className="grid flex-1 grid-cols-1 items-center gap-16 lg:grid-cols-12">
        <div className="animate-fade-up lg:col-span-7" style={{ animationDelay: "80ms" }}>
          <Badge>GDPR • HIPAA • Agentic RAG • Self-Verifying AI</Badge>

          <h1 className="mt-7 text-[2.75rem] leading-[1.08] tracking-tight sm:text-6xl lg:text-[4.5rem]">
            <span className="block font-serif italic text-paper">Every finding</span>
            <span className="block font-sans font-semibold text-paper">
              backed by evidence
            </span>
          </h1>

          <div className="mt-10">
            <PrimaryButton>Start Auditing</PrimaryButton>
          </div>
        </div>

        <div
          className="animate-fade-up flex justify-center lg:col-span-5 lg:justify-end lg:pt-20"
          style={{ animationDelay: "220ms" }}
        >
          <MetricsCard />
        </div>
      </div>

      <div className="animate-fade-in mt-16 grid grid-cols-1 gap-10 border-t border-void-line pt-8 lg:grid-cols-2">
        <p className="max-w-sm text-sm leading-relaxed text-paper-dim">
          Every compliance finding is grounded in retrieved GDPR and HIPAA
          regulations, ensuring conclusions are supported by verifiable
          evidence rather than assumptions.
        </p>

        <div className="lg:justify-self-end">
          <div className="flex flex-wrap gap-2.5">
            <Pill icon={ShieldCheck}>Evidence-Based</Pill>
            <Pill icon={RefreshCcw}>Self-Verifying</Pill>
            <Pill icon={Eye}>Explainable AI</Pill>
          </div>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-paper-dim lg:ml-auto lg:text-right">
            Built with an agentic RAG pipeline, cross-encoder re-ranking, and
            autonomous self-verification to deliver transparent privacy
            audits with explainable regulatory citations.
          </p>
        </div>
      </div>
    </div>
  );
}
