import React, { useState } from 'react';
import { RotateCw, ThumbsUp, RefreshCw, Sparkles, Award } from 'lucide-react';
import type { Flashcard } from '../../api/client';

interface FlipCardDeckProps {
  cards: Flashcard[];
}

export const FlipCardDeck: React.FC<FlipCardDeckProps> = ({ cards }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [masteredCount, setMasteredCount] = useState(0);
  const [reviewDeck, setReviewDeck] = useState<Flashcard[]>(cards);

  if (!reviewDeck || reviewDeck.length === 0) {
    return (
      <div className="bg-[#ffffff] rounded-[2.5rem] p-12 text-center border-2 border-[#6b38d4] chunky-shadow-primary space-y-4 max-w-xl mx-auto">
        <div className="w-20 h-20 bg-[#b2f746] text-[#121f00] border-2 border-[#446900] rounded-full flex items-center justify-center mx-auto chunky-shadow-secondary">
          <Award className="w-10 h-10" />
        </div>
        <h3 className="font-heading text-3xl font-extrabold text-[#181445]">Flashcard Quest Completed! 🎉</h3>
        <p className="text-sm text-[#494454] max-w-sm mx-auto font-medium">
          Awesome job! You've mastered all key terms for this chapter.
        </p>
        <button
          onClick={() => {
            setReviewDeck(cards);
            setCurrentIndex(0);
            setMasteredCount(0);
            setIsFlipped(false);
          }}
          className="px-6 py-3.5 bg-[#6b38d4] text-white font-heading font-extrabold rounded-2xl border-2 border-[#6b38d4] chunky-shadow-primary btn-press cursor-pointer hover:scale-105 transition-transform"
        >
          Restart Deck Practice
        </button>
      </div>
    );
  }

  const currentCard = reviewDeck[currentIndex] || reviewDeck[0];

  const handleGotIt = () => {
    setMasteredCount((prev) => prev + 1);
    nextCard(true);
  };

  const handleStillLearning = () => {
    // Spaced repetition: push card to back of deck
    const updated = [...reviewDeck];
    const [cardToRepeat] = updated.splice(currentIndex, 1);
    updated.push(cardToRepeat);
    setReviewDeck(updated);
    setIsFlipped(false);
  };

  const nextCard = (wasMastered: boolean) => {
    setIsFlipped(false);
    if (wasMastered) {
      const updated = reviewDeck.filter((_, idx) => idx !== currentIndex);
      setReviewDeck(updated);
      if (currentIndex >= updated.length) {
        setCurrentIndex(0);
      }
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      {/* Progress Counter Bar */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-[#ffffff] rounded-2xl border-2 border-[#6b38d4] chunky-shadow-primary">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-[#fb923c]" />
          <span className="font-heading font-extrabold text-sm text-[#181445]">
            Card {currentIndex + 1} of {reviewDeck.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-extrabold text-[#121f00] bg-[#b2f746] px-3.5 py-1 rounded-full border border-[#446900]">
            Mastered: {masteredCount}
          </span>
        </div>
      </div>

      {/* 3D Flip Card */}
      <div 
        onClick={() => setIsFlipped(!isFlipped)}
        className="w-full h-80 cursor-pointer perspective-1000 group"
      >
        <div className={`relative w-full h-full duration-500 transform-style-3d transition-transform ${isFlipped ? 'rotate-y-180' : ''}`}>
          {/* Card Front (Term / Question) */}
          <div className="absolute inset-0 w-full h-full bg-[#ffffff] rounded-[2rem] p-8 border-4 border-[#6b38d4] chunky-shadow-primary flex flex-col justify-between backface-hidden">
            <div className="flex justify-between items-center">
              <span className="px-3.5 py-1 bg-[#efebff] text-[#6b38d4] font-extrabold text-xs rounded-full border border-[#6b38d4]/30">
                {currentCard.term}
              </span>
              <span className="text-xs text-[#7b7486] font-bold flex items-center gap-1">
                <RotateCw className="w-3.5 h-3.5" /> Tap to Flip
              </span>
            </div>

            <div className="text-center my-auto space-y-3">
              <h3 className="font-heading text-2xl font-extrabold text-[#181445]">
                {currentCard.question}
              </h3>
            </div>

            <div className="text-center text-xs font-bold text-[#7b7486]">
              Click anywhere on card to reveal answer
            </div>
          </div>

          {/* Card Back (Answer) */}
          <div className="absolute inset-0 w-full h-full bg-[#b2f746] text-[#121f00] rounded-[2rem] p-8 border-4 border-[#446900] chunky-shadow-secondary flex flex-col justify-between backface-hidden rotate-y-180">
            <div className="flex justify-between items-center">
              <span className="px-3.5 py-1 bg-[#ffffff]/80 text-[#121f00] font-extrabold text-xs rounded-full border border-[#446900]">
                Answer & Explanation
              </span>
              <span className="text-xs text-[#121f00] font-extrabold flex items-center gap-1">
                <RotateCw className="w-3.5 h-3.5" /> Tap to Flip Back
              </span>
            </div>

            <div className="text-center my-auto space-y-2">
              <p className="font-heading text-xl font-extrabold leading-relaxed text-[#121f00]">
                {currentCard.answer}
              </p>
            </div>

            <div className="text-center text-xs font-extrabold text-[#496f00]">
              {currentCard.subject} • Chapter Concept
            </div>
          </div>
        </div>
      </div>

      {/* Got It / Still Learning Buttons */}
      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={handleStillLearning}
          className="flex items-center justify-center gap-2 py-4 bg-[#ffdcc5] hover:bg-[#ffb783] text-[#301400] font-heading font-extrabold rounded-2xl border-2 border-[#904800] chunky-shadow-tertiary btn-press cursor-pointer transition-transform"
        >
          <RefreshCw className="w-5 h-5 text-[#904800]" />
          <span>Still Learning 🔁</span>
        </button>

        <button
          onClick={handleGotIt}
          className="flex items-center justify-center gap-2 py-4 bg-[#b2f746] hover:bg-[#98da27] text-[#121f00] font-heading font-extrabold rounded-2xl border-2 border-[#446900] chunky-shadow-secondary btn-press cursor-pointer transition-transform"
        >
          <ThumbsUp className="w-5 h-5 text-[#446900]" />
          <span>Got It! 👍</span>
        </button>
      </div>
    </div>
  );
};
