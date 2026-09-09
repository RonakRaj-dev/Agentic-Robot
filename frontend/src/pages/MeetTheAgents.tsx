import React from 'react';
import { Bot, BookSearch, Brain, ShieldCheck, CheckCircle2, Zap } from 'lucide-react';

export const MeetTheAgents: React.FC = () => {
  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-12">
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-900 rounded-full font-bold text-xs">
          <Zap className="w-4 h-4 text-emerald-600" />
          <span>Technical Architecture Pitch</span>
        </div>
        <h1 className="font-heading text-4xl font-bold text-slate-900">
          How CurioText AI Works Behind the Scenes
        </h1>
        <p className="text-sm text-slate-600 max-w-xl mx-auto font-medium">
          A high-efficiency, vectorless RAG multi-agent system designed for grounded educational Q&A without vector drift or hallucination.
        </p>
      </div>

      {/* Why Vectorless Explanation Box */}
      <div className="p-8 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-3xl border border-emerald-200 space-y-4">
        <h3 className="font-heading text-2xl font-bold text-emerald-950 flex items-center gap-2">
          <CheckCircle2 className="w-6 h-6 text-emerald-600" />
          Why Vectorless BM25 Search Matters for NCERT
        </h3>
        <p className="text-sm text-emerald-900 leading-relaxed font-medium">
          Traditional vector database embeddings often distort exact mathematical formulas, scientific definitions, or grade-level terminology. Our system utilizes <strong>BM25 exact keyword & text indexing</strong> paired with cross-encoder re-ranking. This guarantees 100% precision, zero embedding cost, zero vector drift, and instant deterministic retrieval.
        </p>
      </div>

      {/* Storyboard Pipeline Diagram */}
      <div className="space-y-6">
        <h2 className="font-heading text-2xl font-bold text-slate-800 text-center">
          The 4-Stage ReAct Execution Pipeline
        </h2>

        <div className="space-y-6">
          {[
            {
              stage: '01',
              title: 'Classroom Supervisor & Validation',
              desc: 'Enforces input sanitization, guards against prompt injections, and applies a 15-second session lock to prevent race conditions.',
              icon: Bot,
              color: '#4EA8DE',
            },
            {
              stage: '02',
              title: 'Vectorless BM25 Retrieval & Re-ranking',
              desc: 'Executes rapid BM25 keyword matching over ingested NCERT chapter text and re-ranks candidate chunks using cross-encoders.',
              icon: BookSearch,
              color: '#FFD166',
            },
            {
              stage: '03',
              title: 'ReAct Teaching Agent Phrasing',
              desc: 'Formulates age-adapted, kid-friendly explanations using Groq LLM inference without inventing facts.',
              icon: Brain,
              color: '#9D4EDD',
            },
            {
              stage: '04',
              title: 'Fact Verification & Egress Formatting',
              desc: 'Cross-checks every claim against source chunks. Formats final response matching Pydantic TeachingResponse contract.',
              icon: ShieldCheck,
              color: '#06D6A0',
            },
          ].map((item) => {
            const IconComp = item.icon;
            return (
              <div
                key={item.stage}
                className="p-6 bg-white rounded-3xl shadow-md border border-slate-100 flex flex-col md:flex-row items-start md:items-center gap-6 hover:shadow-lg transition-shadow"
              >
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center font-heading font-bold text-xl text-slate-900 shrink-0 shadow-sm"
                  style={{ backgroundColor: item.color }}
                >
                  <IconComp className="w-7 h-7" />
                </div>
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-400">STAGE {item.stage}</span>
                    <h3 className="font-heading font-bold text-xl text-slate-900">{item.title}</h3>
                  </div>
                  <p className="text-sm text-slate-600 font-medium leading-relaxed">{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
