import React from 'react';
import { BookOpen, Sparkles, Lightbulb, Video, Layers, Award } from 'lucide-react';
import type { Chapter } from '../../api/client';
import { FormattedMarkdown } from '../common/FormattedMarkdown';


interface ChapterReaderProps {
  chapter: Chapter;
  onOpenVideoPrompt: () => void;
  onGoToFlashcards: () => void;
  onGoToQuiz: () => void;
}

export const ChapterReader: React.FC<ChapterReaderProps> = ({
  chapter,
  onOpenVideoPrompt,
  onGoToFlashcards,
  onGoToQuiz,
}) => {
  return (
    <div className="bg-[#ffffff] rounded-[2rem] p-8 border-2 border-[#6b38d4] chunky-shadow-primary space-y-8">
      {/* Chapter Title Header Banner */}
      <div 
        className="p-6 rounded-[1.5rem] text-[#181445] space-y-3 relative overflow-hidden border-2 border-[#6b38d4]"
        style={{ backgroundColor: chapter.subjectColor + '25' }}
      >
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="px-3.5 py-1 bg-[#ffffff] font-extrabold text-xs rounded-full border border-[#181445]/20 text-[#181445]">
            Class {chapter.classLevel} • {chapter.subject} • Chapter {chapter.chapterNumber}
          </span>

          <button
            onClick={onOpenVideoPrompt}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#6b38d4] text-white font-heading text-xs font-bold rounded-xl border-2 border-[#6b38d4] chunky-shadow-primary btn-press cursor-pointer hover:scale-105 transition-transform"
          >
            <Video className="w-4 h-4" />
            <span>Generate Video Prompt</span>
          </button>
        </div>

        <h1 className="font-heading text-3xl font-extrabold text-[#181445] leading-tight">
          {chapter.title}
        </h1>
        <p className="text-sm font-semibold text-[#494454]">{chapter.subtitle}</p>

        {/* Interactive Quick Links */}
        <div className="flex gap-3 pt-2 flex-wrap">
          <button
            onClick={onGoToFlashcards}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#b2f746] text-[#121f00] text-xs font-extrabold rounded-xl border-2 border-[#446900] chunky-shadow-secondary btn-press cursor-pointer hover:scale-105 transition-transform"
          >
            <Layers className="w-4 h-4" /> Practice Flashcards
          </button>
          <button
            onClick={onGoToQuiz}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#fb923c] text-white text-xs font-extrabold rounded-xl border-2 border-[#904800] chunky-shadow-tertiary btn-press cursor-pointer hover:scale-105 transition-transform"
          >
            <Award className="w-4 h-4" /> Chapter Quiz
          </button>
        </div>
      </div>

      {/* Concept Summary Box */}
      <div className="p-5 bg-[#efebff] rounded-2xl border-2 border-[#6b38d4]/30 text-[#181445] text-sm font-semibold leading-relaxed">
        <span className="font-extrabold text-[#6b38d4]">Chapter Summary: </span>
        {chapter.summary}
      </div>

      {/* Chapter Content Sections (Storybook Card Layout) */}
      <div className="space-y-8">
        {chapter.sections.map((sec) => (
          <div key={sec.id} className="space-y-4 p-6 bg-[#fcf8ff] rounded-[1.5rem] border-2 border-[#cbc3d7] hover:border-[#6b38d4] transition-colors">
            <h3 className="font-heading text-xl font-extrabold text-[#181445] flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-[#6b38d4]" />
              {sec.heading}
            </h3>

            <FormattedMarkdown content={sec.content} className="text-sm text-[#494454] leading-relaxed font-medium" />


            {/* Pull Quote Box */}
            <div className="p-4 bg-[#ffdcc5]/60 rounded-2xl border-l-4 border-[#904800] text-[#301400] text-xs font-bold leading-relaxed flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-[#904800] shrink-0 mt-0.5" />
              <div>
                <p className="uppercase text-[10px] text-[#904800] font-extrabold tracking-wider">Key Takeaway</p>
                <p className="text-sm mt-0.5">{sec.pullQuote}</p>
              </div>
            </div>

            {/* Dig Deeper Expandable Bubble */}
            <div className="p-4 bg-[#cff4fc]/60 rounded-2xl border border-[#0891b2]/40 text-[#0891b2] text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-extrabold text-[#0891b2] uppercase tracking-wider">
                <Lightbulb className="w-4 h-4 text-[#0891b2]" />
                <span>Dig Deeper (Fun Fact)</span>
              </div>
              <p className="text-sm font-semibold">{sec.digDeeper}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
