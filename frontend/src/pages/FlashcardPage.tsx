import React, { useEffect, useState } from 'react';
import { fetchFlashcards } from '../api/client';
import type { Flashcard } from '../api/client';
import { FlipCardDeck } from '../components/flashcard/FlipCardDeck';

interface FlashcardPageProps {
  chapterId: string;
  chapterTitle: string;
  classLevel?: number;
  subject?: string;
}

export const FlashcardPage: React.FC<FlashcardPageProps> = ({
  chapterId,
  chapterTitle,
  classLevel = 6,
  subject = 'Science',
}) => {
  const [cards, setCards] = useState<Flashcard[]>([]);

  useEffect(() => {
    fetchFlashcards(chapterId, classLevel, subject, chapterTitle).then(setCards);
  }, [chapterId, classLevel, subject, chapterTitle]);

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
      {/* Header Badge */}
      <div className="bg-[#ffffff] pixel-border p-6 pixel-corners hard-shadow text-center space-y-2">
        <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-3 py-1 border border-[#1c1b1b] inline-block uppercase">
          🎴 INTERACTIVE ARCADE FLASHCARDS
        </span>
        <h1 className="font-headline font-bold text-3xl text-[#1c1b1b]">
          Chapter Vocabulary: {chapterTitle}
        </h1>
        <p className="font-body text-sm text-[#5d3f3b] max-w-lg mx-auto">
          Tap card to flip between Question and Answer. Mark 'Got It' or 'Still Learning' to track your score!
        </p>
      </div>

      <FlipCardDeck cards={cards} />
    </div>
  );
};
