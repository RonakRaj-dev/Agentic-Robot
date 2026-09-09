import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';
import type { Chapter, VideoPromptPayload } from '../api/client';
import { ChapterReader } from '../components/reader/ChapterReader';
import { AskTheBookPanel } from '../components/chat/AskTheBookPanel';
import { VideoPromptModal } from '../components/video/VideoPromptModal';

interface ChapterExplorerProps {
  chapter: Chapter;
  onGoToFlashcards: () => void;
  onGoToQuiz: () => void;
}

export const ChapterExplorer: React.FC<ChapterExplorerProps> = ({
  chapter,
  onGoToFlashcards,
  onGoToQuiz,
}) => {
  const [showDemoBanner, setShowDemoBanner] = useState(true);
  const [isVideoModalOpen, setIsVideoModalOpen] = useState(false);

  // Default fallback video prompt payload for this chapter
  const chapterVideoPrompt: VideoPromptPayload = {
    visualStyle: chapter.classLevel <= 5 ? '3D Pixar Educational Animation' : '3D Photorealistic Infographic',
    masterPrompt: `Cinematic 3D animation illustrating NCERT Class ${chapter.classLevel} ${chapter.subject} Chapter '${chapter.title}'. Dynamic camera pan across detailed educational environment, soft volumetric lighting, vibrant studio render, 4k ultra-HD.`,
    cameraMotion: 'Slow orbital pan with depth of field',
    scenes: [
      { scene: 1, action: `Visualizing ${chapter.title} concepts`, script: `Welcome to Class ${chapter.classLevel} ${chapter.subject}! Let's explore ${chapter.title}.` },
      { scene: 2, action: 'Demonstrating key textbook diagram', script: 'Observe how each section builds your understanding step-by-step!' }
    ]
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 space-y-6">
      {/* Guided Demo Flow Banner */}
      {showDemoBanner && (
        <div className="p-4 bg-gradient-to-r from-sky-500 to-indigo-600 text-white rounded-2xl shadow-md flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-amber-300 shrink-0" />
            <div className="text-xs">
              <span className="font-bold">Suggested Client Presentation Flow: </span>
              Read Chapter Text ➔ Type a question in Ask-the-Book (watch ReAct steps) ➔ Generate Video Prompt ➔ Try Flashcards & Quiz!
            </div>
          </div>
          <button
            onClick={() => setShowDemoBanner(false)}
            className="text-xs font-bold text-white/80 hover:text-white px-2 py-1 bg-white/10 rounded-lg"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main 2-Column Responsive Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Rich Storybook Chapter Reader (7 cols) */}
        <div className="lg:col-span-7">
          <ChapterReader
            chapter={chapter}
            onOpenVideoPrompt={() => setIsVideoModalOpen(true)}
            onGoToFlashcards={onGoToFlashcards}
            onGoToQuiz={onGoToQuiz}
          />
        </div>

        {/* Right Column: ReAct Agent Chat Panel (5 cols) */}
        <div className="lg:col-span-5 sticky top-20">
          <AskTheBookPanel
            classLevel={chapter.classLevel}
            subject={chapter.subject}
            chapterTitle={chapter.title}
          />
        </div>
      </div>

      {/* Video Generation Prompt Modal */}
      <VideoPromptModal
        isOpen={isVideoModalOpen}
        onClose={() => setIsVideoModalOpen(false)}
        classLevel={chapter.classLevel}
        subject={chapter.subject}
        chapterTitle={chapter.title}
        videoPrompt={chapterVideoPrompt}
      />
    </div>
  );
};
