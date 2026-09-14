import React, { useState, useEffect } from 'react';
import type { Flashcard } from '../api/client';
import { fetchFlashcards } from '../api/client';
import { ArcadeLoader } from '../components/ArcadeLoader';

interface FlashcardScreenProps {
  chapterId: string;
  chapterTitle: string;
  classLevel: number;
  subject: string;
}

export const FlashcardScreen: React.FC<FlashcardScreenProps> = ({
  chapterId,
  chapterTitle,
  classLevel,
  subject,
}) => {
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [masteredSet, setMasteredSet] = useState<Set<number>>(new Set());

  useEffect(() => {
    setIsLoading(true);
    fetchFlashcards(chapterId, classLevel, subject, chapterTitle).then((fetched) => {
      setCards(fetched || []);
      setCurrentIndex(0);
      setMasteredSet(new Set());
      setIsFlipped(false);
      setIsLoading(false);
    }).catch(() => {
      setIsLoading(false);
    });
  }, [chapterId, classLevel, subject, chapterTitle]);

  const card = cards[currentIndex] || {
    term: `Class ${classLevel} Key Concept`,
    question: `What is the core principle of ${chapterTitle}?`,
    answer: `Understanding fundamentals through practical observation and evidence in ${subject}.`,
  };

  const handleNext = (gotIt: boolean) => {
    if (gotIt) {
      setMasteredSet((prev) => new Set(prev).add(currentIndex));
    }
    setIsFlipped(false);
    if (currentIndex < Math.max(cards.length - 1, 0)) {
      setCurrentIndex((i) => i + 1);
    } else {
      // Loop back to start cleanly if reached end
      setCurrentIndex(0);
    }
  };

  const totalCards = Math.max(cards.length, 10);
  const masteredCount = Math.min(masteredSet.size, totalCards);

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-16 pb-24 w-full h-full max-w-5xl mx-auto overflow-y-auto">
      {/* Header */}
      <div className="flex justify-between items-center pb-4 mb-6 border-b-[3px] border-[#1c1b1b]">
        <div>
          <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-3 py-1 border border-[#1c1b1b] inline-block uppercase">
            🎴 FLASHCARDS • CLASS {classLevel} {subject}
          </span>
          <h2 className="font-headline font-bold text-2xl text-[#1c1b1b] mt-1">
            {chapterTitle}
          </h2>
        </div>

        <div className="bg-[#ffffff] border-[3px] border-[#1c1b1b] px-4 py-2 brutal-shadow font-pixel text-xs font-bold text-[#006b27]">
          MASTERED: {masteredCount} / {totalCards}
        </div>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center my-auto py-8">
          <ArcadeLoader
            title="Loading Flashcards..."
            subtitle={`Preparing notes for ${chapterTitle}...`}
            defaultVariant="scifi-server"
          />
        </div>
      ) : (
        /* 3D Upside Down Flip Flashcard Container */
        <div className="flex-1 flex flex-col items-center justify-center max-w-2xl mx-auto w-full my-auto [perspective:1000px]">

        <div
          onClick={() => setIsFlipped(!isFlipped)}
          className={`w-full min-h-[340px] relative transition-transform duration-700 [transform-style:preserve-3d] cursor-pointer ${
            isFlipped ? '[transform:rotateX(180deg)]' : ''
          }`}
        >
          {/* Card Front */}
          <div className="absolute inset-0 w-full h-full bg-[#ffffff] border-[3px] border-[#1c1b1b] brutal-shadow-lg pixel-corners p-8 flex flex-col justify-between [backface-visibility:hidden]">
            <div className="flex justify-between items-center">
              <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-2 py-0.5 border border-[#1c1b1b]">
                CARD {currentIndex + 1} OF {totalCards}
              </span>
              <span className="font-pixel text-xs font-bold text-[#5d3f3b]">
                QUESTION (FRONT)
              </span>
            </div>

            <div className="my-auto text-center space-y-3">
              <span className="font-pixel text-xs font-bold text-[#006b27] bg-[#72fe88] px-2.5 py-1 border border-[#1c1b1b] inline-block uppercase">
                {card.term || 'CONCEPT'}
              </span>
              <h3 className="font-headline font-black text-2xl md:text-3xl text-[#1c1b1b]">
                {card.question}
              </h3>
              <p className="font-pixel text-xs font-bold text-[#bc000a] animate-pulse">
                [TAP CARD TO FLIP UPSIDE DOWN]
              </p>
            </div>

            <div className="text-right">
              <span className="font-pixel text-[11px] font-bold text-[#5d3f3b]">
                NCERT CHAPTER VOCABULARY
              </span>
            </div>
          </div>

          {/* Card Back (Upside-Down Rotated 180 deg) */}
          <div className="absolute inset-0 w-full h-full bg-[#fecb00] border-[3px] border-[#1c1b1b] brutal-shadow-lg pixel-corners p-8 flex flex-col justify-between [backface-visibility:hidden] [transform:rotateX(180deg)]">
            <div className="flex justify-between items-center">
              <span className="font-pixel text-xs font-bold text-[#6e5700] bg-[#ffffff] px-2 py-0.5 border border-[#1c1b1b]">
                CARD {currentIndex + 1} OF {totalCards}
              </span>
              <span className="font-pixel text-xs font-bold text-[#6e5700]">
                ANSWER (FLIPPED BACK)
              </span>
            </div>

            <div className="my-auto text-center space-y-3">
              <span className="font-pixel text-xs font-bold text-white bg-[#bc000a] px-2.5 py-1 border border-[#1c1b1b] inline-block uppercase">
                ANSWER EXPLANATION
              </span>
              <p className="font-headline font-bold text-xl md:text-2xl text-[#1c1b1b] leading-relaxed">
                {card.answer}
              </p>
            </div>

            <div className="text-right">
              <span className="font-pixel text-[11px] font-bold text-[#6e5700]">
                TAP AGAIN TO FLIP FRONT
              </span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex gap-4 w-full mt-8">
          <button
            onClick={() => handleNext(false)}
            className="flex-1 py-4 bg-[#f0eded] text-[#1c1b1b] font-pixel text-xs font-bold uppercase border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active cursor-pointer"
          >
            STILL LEARNING
          </button>
          <button
            onClick={() => handleNext(true)}
            className="flex-1 py-4 bg-[#72fe88] text-[#002107] font-pixel text-xs font-bold uppercase border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active cursor-pointer"
          >
            GOT IT! ✔
          </button>
        </div>
      </div>
      )}
    </div>
  );
};

